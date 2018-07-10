# -*- coding: utf-8 -*-

from types import *
from dwfconstants import *
import time
import numpy as np
import fitSine as fs
import sys 				# update

# System parameter
Rref = 0.982e6 	# Rref is a system parameter 0.982Mohm
CS = 140e-12 	# CS is PCB stray cap and a system parameter 140pF
bufferSize = 1024
bufferCount = 2			# Number of cycles in data buffer
totalBufferSize = bufferSize*bufferCount

bufferData0 = (c_double*totalBufferSize)() # For source channel
bufferData1 = (c_double*totalBufferSize)() # For destination channel

# update OS Check
if sys.platform.startswith("win32"): # for windows OS
	dwf = cdll.dwf
elif sys.platform.startswith("darwin"):	# for Mac OS
	dwf = cdll.LoadLibrary("libdwf.dylib")
else:
	dwf = cdll.LoadLibrary("libdwf.so")

handleDwf = c_int()

def initialize():
	print("### Initilaize the device")
	res = dwf.FDwfDeviceOpen(-1, byref(handleDwf))

	if(res):
		print("- Opening device successed!")
	else:
		print("- Opening device failed! please restart program.")
		quit()

	# enable positive supply
	dwf.FDwfAnalogIOChannelNodeSet(handleDwf, c_int(0), c_int(0), c_double(True))

	# set voltage to 5V
	dwf.FDwfAnalogIOChannelNodeSet(handleDwf, c_int(0), c_int(1), c_double(5))

	# enable negative supply
	dwf.FDwfAnalogIOChannelNodeSet(handleDwf, c_int(1), c_int(0), c_double(True))

	# set voltage to -5V
	dwf.FDwfAnalogIOChannelNodeSet(handleDwf, c_int(1), c_int(1), c_double(-5))

	# master enable
	dwf.FDwfAnalogIOEnableSet(handleDwf, c_int(True))

	print("### Setting the channels")

	dwf.FDwfAnalogOutNodeEnableSet(handleDwf, c_int(0), AnalogOutNodeCarrier, c_int(True))

	# configure enabled channels
	dwf.FDwfAnalogOutNodeFunctionSet(handleDwf, c_int(0), AnalogOutNodeCarrier, funcSine)
	dwf.FDwfAnalogOutNodeAmplitudeSet(handleDwf, c_int(0), AnalogOutNodeCarrier, c_double(1)) #1V amplitude

	dwf.FDwfAnalogOutNodeOffsetSet(handleDwf, c_int(0), AnalogOutNodeCarrier, c_double(0))  #LM6172 Amp
	time.sleep(1)

	# Setting the buffer and channel.
	dwf.FDwfAnalogInTriggerAutoTimeoutSet(handleDwf, c_double(0)) #disable auto trigger
	dwf.FDwfAnalogInTriggerSourceSet(handleDwf, trigsrcDetectorAnalogIn) #one of the analog in channels
	dwf.FDwfAnalogInTriggerTypeSet(handleDwf, trigtypeEdge)
	dwf.FDwfAnalogInTriggerChannelSet(handleDwf, c_int(0)) # first channel
	dwf.FDwfAnalogInTriggerLevelSet(handleDwf, c_double(0)) # 0V
	dwf.FDwfAnalogInTriggerConditionSet(handleDwf, trigcondRisingPositive)

	# enable output/mask on 8 LSB IO pins, from DIO 0 to 7
	dwf.FDwfDigitalIOOutputEnableSet(handleDwf, c_int(0x000F))

	print("- Setting the channels ended!")

def polar2RC(freq, gain, phase):
	w = 2*np.pi*freq 			# freq. is input
	G = gain*np.exp(1j*phase)
	Z = G/(1-G)*Rref			# Rref is a system parameter 0.982Mohm
	Zc = 1/(1/Z-1j*w*CS) 		# CS is PCB stray cap and a system parameter
	return Zc

def ZC2polar(freq, Zc):
	w = 2*np.pi*freq
	Rc = np.real(Zc)
	Cc = 1/(w*np.imag(Zc))*-1e9

	return Rc, Cc

def measureImpedance(channels, freqs):
	channelCount = len(channels)
	freqCount = len(freqs)

	print("MeasureImpedance called : channel(%d), freq(%d)" % (channelCount, freqCount))

	result = [[0]*freqCount for _ in range(channelCount)]
	for indexChannel in range(channelCount):
		channel = channels[indexChannel]
		# setting the channel setting
		dwf.FDwfDigitalIOOutputSet(handleDwf, c_int(0x08|channel))
		# wait for the stable channel
		for indexFreq in range(freqCount):
			freq = freqs[indexFreq]
			# setting the frequency
			dwf.FDwfAnalogOutNodeFrequencySet(handleDwf, c_int(0), AnalogOutNodeCarrier, c_double(freq))
			# enable function generator and wait for stable
			dwf.FDwfAnalogOutConfigure(handleDwf, c_int(0), c_bool(True))
			time.sleep(0.1)
			actualFreq = c_double()
			dwf.FDwfAnalogOutNodeFrequencyGet(handleDwf, c_int(0), AnalogOutNodeCarrier, byref(actualFreq))

			# Sampling frequency calculation, set 2*period less than
			vlen = totalBufferSize + 1
			tT = bufferSize + 1
			while vlen > totalBufferSize:
				tT = tT - 1
				sf = actualFreq.value*tT
				analogFreq = c_double()
				dwf.FDwfAnalogInFrequencySet(handleDwf, c_double(sf))
				dwf.FDwfAnalogInFrequencyGet(handleDwf, byref(analogFreq))
				vlen = int(2*analogFreq.value/actualFreq.value)

			# beginning acquisition and wait for completion
			dwf.FDwfAnalogInConfigure(handleDwf, c_bool(False), c_bool(True))
			status = c_byte()
			while True:
				# waiting the configuration is done
				dwf.FDwfAnalogInStatus(handleDwf, c_int(1), byref(status))
				# value acquisition is done
				if status.value == DwfStateDone.value:
					break
				time.sleep(0.1)

			# getting the data
			dwf.FDwfAnalogInStatusData(handleDwf, c_int(0), bufferData0, totalBufferSize)
			dwf.FDwfAnalogInStatusData(handleDwf, c_int(1), bufferData1, totalBufferSize)

			# sine matching
			data0 = list(bufferData0[1:vlen])
			data1 = list(bufferData1[1:vlen])
			R0, T0, M0 = fs.sineFit2Cycle(data0, bufferCount)
			R1, T1, M1 = fs.sineFit2Cycle(data1, bufferCount)

			if R0 < 0:
				R0 = -R0
				T0 = T0-np.pi
			if R1 < 0:
				R1 = -R1
				T1 = T1-np.pi

			g = R1/R0/100 # g*1M/100
			p = T1-T0
			if p > np.pi:
				p -= np.pi*2

			z = polar2RC(freq, g, p)
			result[indexChannel][indexFreq] = z
	return result

def checkChip():
	result = {
		'Rc' : [],
		'Cc' : [],
		'valid' : []
	}

	print("Check chip called()")
	defaultFreq = 4000
	channels = range(8) # all channels
	freqs = [defaultFreq]		# default frequency
	# getting the impedance with default values
	Z = measureImpedance(channels, freqs)

	for index in range(len(Z)):
		Rc, Cc = ZC2polar(defaultFreq, Z[index])

		valid = False

		# 에러라고 인식하는 범위
		# Rc[0]이 30K보다 크면 셀이 비어있거나 칩 연결이 제대로 되지 않았을 것.
		if(Rc[0] <= 1000 * 30):	# 테스트 값: 100K, 릴리즈용: 30K
			valid = True

		result['Rc'].append(float("{0:.1f}".format(Rc[0])))
		result['Cc'].append(float("{0:.1f}".format(Cc[0])))
		result['valid'].append(valid)

	print(result)
	return(result)
