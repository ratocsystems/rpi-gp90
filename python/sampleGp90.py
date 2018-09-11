#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import sys
import os
import time
import argparse
import math
import smbus            #I2C制御用
import RPi.GPIO as GPIO #GPIO制御用


# グローバル変数
                        # サーボモータSG90
sg90pre = 101           # PWM周期60Hz  Prescale:101=60Hz  25MHz/4096/101≒ 60Hz
sg90max = 595           # PWM H期間最大 2400us
sg90mid = 360           # PWM H期間中間 1450us
sg90min = 125           # PWM H期間最小  500us
sg90mul = 4             # エンコーダ乗数

# RPi-GP90初期化
def init_GP90():   
    GPIO.setmode(GPIO.BCM)                                # Use Broadcom pin numbering
    GPIO.setup(27,   GPIO.OUT, initial=GPIO.LOW )         # RPi-GP90絶縁電源OFF
    time.sleep(0.5)                                       # 電源リセット待ち
    GPIO.output(27, True)                                 # RPi-GP90の絶縁電源ON
    time.sleep(0.5)                                       # 電源安定待ち

# PWM PCA9685 初期化＋Prescale設定
#   adrs:PWM-I2Cアドレス(0x40-0x4F), prescale:プリスケール値(0-4095)
def init_pwm(adrs, prescale):
    mode1 = i2c.read_byte_data(adrs, 0x00)                # MODE1設定値読み込み
    i2c.write_byte_data(adrs, 0x00, (mode1 & 0x7f)|0x30 ) # SLEEPモードへ Auto-Increment有効
    i2c.write_byte_data(adrs, 0xfe, prescale)             # Prescale値書き込み
    i2c.write_byte_data(adrs, 0x00, (mode1 & 0x6f)|0x20 ) # SLEEPモード解除 Auto-Increment有効
    time.sleep(0.005)                                     # 500us PCA9685内部発振器安定待ち
    i2c.write_byte_data(adrs, 0x00, (mode1 & 0x6f)|0xA0 ) # リスタート Auto-Increment有効

# PWM PCA9685 出力制御
#   adrs:PWM-I2Cアドレス(0x40-0x4F), ch:PWM-ch(0-15), hi:H遷移(0-4095), lo:L遷移(0-4095) 
def write_pwm(adrs, ch, hi, lo):
    i2c.write_word_data(adrs, 0x06+(ch*4), hi)            # H遷移タイミング設定
    i2c.write_word_data(adrs, 0x08+(ch*4), lo)            # L遷移タイミング設定

# エンコーダのカウント読み込みとPWM値変換
#   adrs:カウンタI2Cアドレス(0x30), ch:パルスch(0-3)
def get_enccnt( adrs, ch ):
    pwm = i2c.read_word_data(adrs, (ch<<3)+0x06)          # PULS ch のカウントレジスタ読み込み
    pwm *= sg90mul                                        # ×乗数
    pwm = (pwm + sg90mid) & 0xffff                        # PWMオフセット加算
    return pwm

# エンコーダカウントでSG90のサーボ駆動
def pwm_test( adrs, ch ):
    event = i2c.read_word_data(pccadrs, 0x20)             # EVENTレジスタ読み込み
    pa = get_enccnt(pccadrs, 0)                           # ch0 のエンコーダカウント値
    if( event & (1<<((ch % 4)<<2)) ):
        if( (pa >= sg90min) and (pa <= sg90max) ):
            write_pwm(adrs, ch, 0, pa)                    # PWMa タイミング設定
    return pa

# メイン
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                prog='sampleGp90.py',          #プログラムファイル名
                usage='RPi-GP90のサンプルプログラム', #使用方法
                description='引数なし',
                epilog=     '--------------------------------------------------------------------------',
                add_help=True,
                )
    try:
    
        # RaspberryPi I2C機能設定
        i2c  = smbus.SMBus(1)       # RPi-GP90はI2C1を使用
        pwmadrs = 0x40              # PWMコントローラ    PCA9685 I2Cアドレス 0x40 (A3～A0)
        pccadrs = 0x30              # パルスカウント制御 STM32F0 I2Cアドレス 0x30

        # RPi-GP90初期化
        init_GP90()

        print( "RPi-GP90 サンプルプログラム" )
        key = 1

        init_pwm( pwmadrs, sg90pre )    # PWM初期化

        while( key != 0 ):
            i = input( "1:PWMテスト 2:カウンタテスト 3:ロータリーエンコーダ＋サーボモータテスト 0:終了 > " )
            if( len(i) == 0 ):
                continue
            key = int(i,10)
            if( key == 0 ):         # '0'なら、
                break               # プログラム終了

            # PWMコントローラ PCA9685 のテスト
            while( key == 1 ):      # '1'なら、PWMテスト
                i = input( "PWM 周波数[Hz](24-1526) 0:戻る > " )    # PWMの周波数を入力する
                if( len(i) == 0 ):
                    continue
                pwmfreq = int(i,10)
                if( pwmfreq == 0 ):                       # 0なら初期メニューに戻る
                    break
                pwmpres_f = 25000000.0 / 4096.0 / float(pwmfreq) - 1.0  # 周波数からプリスケール値算出
                pwmpres = int(math.floor(pwmpres_f + 0.5))          # Prescale = 25MHz/4096/pwmfreq[Hz]-1
                print( "プリスケール値= {0}" .format(pwmpres) )
                init_pwm( pwmadrs, pwmpres )                        # PWM Prescale値で初期化
                while( 1 ):
                    i = input( "PWM チャンネル(0-15) -1:戻る > " )  # PWMパルス出力するch番号を入力する
                    pwmch = int(i,10)
                    if( (pwmch < 0) or (pwmch > 15) ):        # 範囲外なら周波数設定に戻る
                        break
                    i = input( "PWM パルスH (0-4095) -1:戻る > " )  # PWMパルスがL->Hへ変化するタイミングを入力する 4096分解能
                    pwmhi = int(i,10)
                    if( (pwmhi < 0) or (pwmhi > 4095) ):      # 範囲外なら周波数設定に戻る
                        break
                    i = input( "PWM パルスL (0-4095) -1:戻る > " )  # PWMパルスがH->Lへ変化するタイミングを入力する 4096分解能
                    pwmlo = int(i,10)
                    if( (pwmlo < 0) or (pwmlo > 4095) ):      # 範囲外なら周波数設定に戻る
                        break
                    period = 40.0*float(pwmpres)
                    print( "PWM ch%d に %8.4f[ms]周期 %8.4f[ms]H期間 %8.4f[ms]遅延 でパルス出力開始" %
                        ( pwmch, period*4096.0/1000000.0, period*float(pwmlo-pwmhi)/1000000.0, period*float(pwmhi)/1000000.0 ) )
                    write_pwm(pwmadrs, pwmch, pwmhi, pwmlo)   # PWMタイミング設定

            # パルスカウントコントローラSTM32のテスト
            while( key == 2 ):      # '2'なら、カウンタテスト
                rdat = i2c.read_i2c_block_data(pccadrs, 0x00, 0x20)  # レジスタアドレス 00h～1Fh データ読み込み
                print( "    +00  +02  +04  +06  +08  +0A  +0C  +0E", end="" ) # 一覧表示
                for radr in range(0x10):                      # レジスタアドレス0x00-0x1F
                    if( (radr % 0x08)==0x00 ):                # 8Wordデータごとに、
                        print( "" )                           # 改行
                        print( "%02X:" % (radr*2), end="" )   # アドレス表示
                    print("%04X " % (rdat[radr*2]|(rdat[radr*2+1]<<8)), end="" )  # データ表示
                print( "" )                                   # 改行
                i = input( "レジスタアドレス(0x00-0x1E,0x20 HEX) D:一覧 B:戻る > 0x" ) # 書き換えるレジスタアドレスを入力する
                if( len(i) == 0 ):
                    continue                                  # 一覧に戻る
                radr = int(i,16)
                if( radr==0x0d ):                             # 'D'isp
                    continue                                  # 一覧に戻る
                if( (radr<0)or(radr>0x20)or(radr==0x0b) ):    # 'B'ackか範囲外なら、
                    break                                     # 初期メニューに戻る。
                if( radr==0x20 ):                             # レジスタアドレス0x20(イベントレジスタ)なら、
                    i = i2c.read_word_data(pccadrs, radr)     # wordデータを読み込み、
                    print( "イベント=0x%04X" % i )            # HEX４桁で表示して、
                    continue                                  # 一覧に戻る。
                i = input( "書き込みデータ(4桁HEX) > 0x" )    # 書き換えるデータ(16bit)を入力する
                wdat = int(i,16)
                i2c.write_word_data(pccadrs, radr, wdat)      # wordデータ書き込み

            # ロータリーエンコーダ＋サーボモータテスト
            # PWM-ch0にサーボモータSG90を接続し、PULSE-ch0にロータリーエンコーダ(ALPS EC12)を接続
            while( key == 3 ):      # '3'なら、ロータリーエンコーダとサーボモータの組み合わせテスト
                init_pwm( pwmadrs, sg90pre )                  # PWM Prescale値で初期化
                pwmch = 0                                     # PWM ch 0
                write_pwm(pwmadrs, pwmch, 0, sg90mid)         # PWMタイミング設定 SG90中間点
                i2c.write_word_data( pccadrs, 0x00, 0x300F ); # Pulse ch0 ２相パルス計測設定
                print( "PULSE-ch0にロータリーエンコーダ[EC12]を接続してください。" )
                print( "外部電源入力に5V電源を接続してください。" )
                print( "PWM-ch%dにサーボモータ[SG90]を接続してください。" % pwmch )
                i=input( "準備ができたらEnterキーを押してください 0:終了 > " )
                if( len(i) != 0 ):
                    break
                i2c.write_word_data( pccadrs, 0x06, 0x0000 );  # ch0 カウンタクリア
                print( "つまみと連動してサーボモータが動作することを確認してください。" )
                print( " （終了：つまみを最大まで回す）" )
                while( 1 ):
                    pwma = pwm_test( pwmadrs, pwmch )         # 連動動作
                    if( pwma >= sg90max ):
                        break

    except KeyboardInterrupt:       # CTRL-C キーが押されたら、
         print( "中断しました" )    # 中断
#    except Exception:               # その他の例外発生時
         print( "エラー" )          # エラー
    GPIO.output(27, False)          # RPi-GP90の絶縁電源OFF
    GPIO.cleanup()
    sys.exit()
