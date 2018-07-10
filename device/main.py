# -*- coding: utf-8 -*-
# Date : 2017.01.02 ~
# Author : Jun Yeon

from ctypes import *
import threading
import dwf
import ast
import json
import datetime
# for protocol values
import protocol as Protocol

import numpy as np

# for request by http
import requests
import time

from requests.exceptions import ConnectionError

# Loading the dwf library
state = Protocol.STATE_INITIALIZNG
recordState = Protocol.RECORD_STATE_OFF
deadlineTime = datetime.datetime.now()

server_ip = "127.0.0.1"
print("connect to Server[" + server_ip + "]")

config = {
	'freq' : [],
	'channel' : [],
	'period' : 1,
	'deadline' : 0,
	'counter' : 0
}

def checkConfig():
	if(len(config['freq']) == 0) or (len(config['channel']) == 0) or (config['deadline'] == 0):
		return False
	return True

# send the messaage to server for setting the state
def setParameter(key, value):
	data = {
		'menu' :  0, # 0 is set
		'key' : key,
		'value' : value
	}

	while(True):
		try:
			response = requests.post('http://' + server_ip + ':8000/state/', json.dumps(data))
			response = response.content
			jsonResult = json.loads(response)

			if(jsonResult['result']):
				break
			else:
				time.sleep(0.1)
		except ConnectionError as e:
			print("setParameter() not working..retry..(internet connection failed)")
			time.sleep(5)

	# print('setParameter %s(%s) result : %s' % (key, value, response.content))

def getParameter(key):
	data = {
		'menu' : 1, # 1 is get
		'key' : key
	}

	while(True):
		try:
			response = requests.post('http://' + server_ip + ':8000/state/', json.dumps(data))
			response = response.content
			jsonResult = json.loads(response)
			# print('getParameter %s : %s' % (key, jsonResult))
			if(jsonResult['result']):
				return jsonResult['value']
			else:
				return ''
		except ConnectionError as e:
			print("getParameter() not working..retry..(internet connection failed)")
			time.sleep(5)


def pushResultData(currentTime, timeFormat):
	global deadlineTime

	resultData = {
		'menu' : 'result'
	}

	targetTime = currentTime + datetime.timedelta(days=config['deadline'])

	resultData['dataCounter'] = config['counter']
	resultData['startTime'] = currentTime.strftime(timeFormat)
	resultData['targetTime'] = (targetTime).strftime(timeFormat)
	resultData['period'] = config['period']
	resultData['freqs'] = config['freq']
	resultData['channels'] = config['channel']

	deadlineTime = targetTime

	while(True):
		try:
			response = requests.post('http://' + server_ip + ':8000/collector/', json.dumps(resultData))
			response = response.content
			jsonResult = json.loads(response)
			print('pushResultData result %s' % (jsonResult['result']))
			return jsonResult['result']
		except ConnectionError as e:
			print("pushResultData() not working..retry..(internet connection failed)")
			time.sleep(5)


def pushScopeData(sendData):
	sendData['menu'] = 'scope'

	while(True):
		try:
			response = requests.post('http://' + server_ip + ':8000/collector/', json.dumps(sendData))
			response = response.content
			print(response)
			jsonResult = json.loads(response)
			print('pushScopeData result %s' % (jsonResult['result']))
			return jsonResult['result']
		except ConnectionError as e:
			print("pushScopeData() not working..retry..(internet connection failed)")
			time.sleep(5)


# remove previous server data
def initConfiguration():
	while(True):
		try:
			response = requests.post('http://' + server_ip + ':8000/init/')
			print('initParameter result : %s' % response.content)
			break
		except ConnectionError as e:
			print("initConfiguration() not working..retry..(internet connection failed)")
			time.sleep(5)


# Measure the impedance and send to server
class MeasureTimer(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.event = threading.Event()
		self.startTime = datetime.datetime.now()

	def stop(self):
		self.event.set()

	def setStartTime(self, currentTime):
		self.startTime = currentTime

	def run(self):
		global recordState
		global elaspedTime
		global config
		global state
		global deadlineTime

		print("# measure thread start!")

		channels = config['channel']
		freqs = config['freq']
		dataCounter = config['counter']
		period = config['period']

		while(not self.event.is_set()):
			currentTime = datetime.datetime.now()
			timeFormat = '%Y-%m-%d %H:%M:%S'

			sendData = {
				'dataCounter' : dataCounter,
				'time' : currentTime.strftime(timeFormat),
				'timeMin' : ((currentTime - self.startTime).total_seconds() // 60),
				'Z' : [],
				'R' : [],
				'C' : [],
				'freq' : [],
				'channel' : []
			}

			# measure the impedance
			resultRawData = dwf.measureImpedance(channels, freqs)

			# separate the datas
			for channelIdx in range(len(channels)):
				for freqIdx in range(len(freqs)):
					Zc = resultRawData[channelIdx][freqIdx]
					Rc, Cc = dwf.ZC2polar(freqs[freqIdx], Zc)
					Rc = Rc.tolist()
					Zc_result = np.sqrt(Zc.real*Zc.real + Zc.imag*Zc.imag)

					sendData['Z'].append(float("{0:.1f}".format(Zc_result)))
					sendData['R'].append(float("{0:.1f}".format(Rc)))
					sendData['C'].append(float("{0:.1f}".format(Cc)))
					sendData['freq'].append(freqs[freqIdx])
					sendData['channel'].append(channels[channelIdx])

			# Check the timeout
			if(currentTime > deadlineTime):
				print("# measurement deadline arrvied!")
				break

			# send data to server if record state is on.
			if recordState == Protocol.RECORD_STATE_ON:
				print('# Recording is on.. sending the data to server')
				print(sendData)
				pushScopeData(sendData)

			# checking the this thread is stopped
			counter = 0
			totalCount = period * 60
			flag = False

			# checking per second
			while(counter < totalCount):
				currentTime = datetime.datetime.now()
				time.sleep(1)
				counter += 1

				print("counter %d/%d " % (counter, totalCount))

				# Check the timeout
				if(currentTime > deadlineTime):
					print("# measurement deadline arrvied!")
					flag = True
					break

				# checking if the stop command arrived.
				if self.event.is_set():
					print("# measure thread stop set!")
					break

			if(flag):
				break

		print("# measure thread stopped!")
		state = Protocol.STATE_READY
		config = {}
		deadlineTime = datetime.datetime.now()

# measure timer
measureTimer = MeasureTimer()

checkChipFlag = False	# update
# Start the thread that monitoring of the server
def monitorCommand():
	global state
	global recordState
	global measureTimer
	global elaspedTime
	global config
	global deadlineTime
	global checkChipFlag	# update
	configCommand = getParameter(Protocol.PARAM_COMMAND)
	recordState = getParameter(Protocol.PARAM_RECORD_STATE)

	if configCommand:
		if(configCommand == Protocol.COMMAND_START):
			if(state == Protocol.STATE_SETUP_OK):
				# TODO[3]: Checking the setup parameter
				# and if the parameter is valid, going the start
				# but not valid parameter, set the error state
				if(checkConfig()):
					currentTime = datetime.datetime.now()
					timeFormat = '%Y-%m-%d %H:%M:%S'
					res = pushResultData(currentTime, timeFormat)
					print("start ok and result %d" % res)

					if(res):
						state = Protocol.STATE_RUNNING
						setParameter(Protocol.PARAM_START_TIME, currentTime.strftime(timeFormat))
						setParameter(Protocol.PARAM_RESULT, 'OK')
						measureTimer = MeasureTimer()
						measureTimer.setStartTime(currentTime)
						measureTimer.start()
					else:
						setParameter(Protocol.PARAM_ERROR, 'Set the result data failed.')
						setParameter(Protocol.PARAM_RESULT, 'FAILED')
				else:
					# setting the error
					setParameter(Protocol.PARAM_ERROR, 'Not setup')
					setParameter(Protocol.PARAM_RESULT, 'FAILED');
			else:
				setParameter(Protocol.PARAM_ERROR, 'Not setup')
				setParameter(Protocol.PARAM_RESULT, 'FAILED');

		elif(configCommand == Protocol.COMMAND_STOP):
			if(state == Protocol.STATE_RUNNING):
				measureTimer.stop()
				setParameter(Protocol.PARAM_RESULT, 'OK');
			else:
				setParameter(Protocol.PARAM_ERROR, 'Not running device.')
				setParameter(Protocol.PARAM_RESULT, 'FAILED');
		elif(configCommand == Protocol.COMMAND_CHECKCHIP):
			if((state == Protocol.STATE_READY) or (state == Protocol.STATE_SETUP_OK) or (state == Protocol.STATE_RUNNING)):			# update
				if(checkChipFlag):																# update
					setParameter(Protocol.PARAM_RESULT, 'USING')								# update
				else:
					checkChipFlag = True				# update
					resultValue = dwf.checkChip()

					# saving the valid chip information
					setParameter(Protocol.PARAM_CHIPINFO, json.dumps(resultValue))
					setParameter(Protocol.PARAM_RESULT, 'OK')

					checkChipFlag = False				# udpate
			else:
				setParameter(Protocol.PARAM_RESULT, 'FAILED')

		elif(configCommand == Protocol.COMMAND_SETUP):
			# TODO[2]: Getting the channels and frequencies, deadline date.
			if(state == Protocol.STATE_READY) or (state == Protocol.STATE_SETUP_OK):
				# getting the channels and freq, deadline
				channels = getParameter(Protocol.PARAM_CHANNEL)
				freqs = getParameter(Protocol.PARAM_FREQ)
				deadline = getParameter(Protocol.PARAM_DEADLINE)
				period = getParameter(Protocol.PARAM_PERIOD)
				counter = getParameter(Protocol.PARAM_COUNTER)

				# change to list type
				config['channel'] = ast.literal_eval(channels)
				config['freq'] = ast.literal_eval(freqs)
				config['deadline'] = int(deadline)
				config['period'] = int(period)
				config['counter'] = int(counter)

				state = Protocol.STATE_SETUP_OK
				setParameter(Protocol.PARAM_RESULT, 'OK')

			else:
				setParameter(Protocol.PARAM_ERROR, 'Unknown')
				setParameter(Protocol.PARAM_RESULT, 'FAILED')

	# update current state into the ini file
	setParameter(Protocol.PARAM_STATE, state)

	# remove current command
	setParameter(Protocol.PARAM_COMMAND, '')

	# restart the timer
	threading.Timer(5, monitorCommand).start()

# initialize the system

# TODO, if same system is working, error message will be occured


initConfiguration()
monitorCommand()
dwf.initialize()

"""
test = MeasureTimer()

config['freq'].append(4000)
config['freq'].append(10000)
config['freq'].append(20000)

config['channel'].append(0)
config['channel'].append(1)
config['channel'].append(2)
config['channel'].append(4)

test.setConfig(config)
test.start()
"""

# end of initilizing device
state = Protocol.STATE_READY

print('### Finishing the initialize..')

while(True):
	pass
