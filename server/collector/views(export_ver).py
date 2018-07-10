# Date : 2017.01.02 ~
# Author : Jun Yeon

from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from ConfigParser import RawConfigParser
from . import protocol as STATE
from collector.models import *
from django.db.models import Max
from chartit import DataPool, Chart

import django_excel as excel

import json
import time
import ast
import datetime
import random

import matplotlib
import matplotlib.pyplot as plt


# This web server only manages the device's status, data.
# Not handle the device's state, only bypass the commands.

# for setting the config
def initConfig():
	setConfig(STATE.PARAM_STATE, STATE.STATE_INITIALIZNG)
	setConfig(STATE.PARAM_COMMAND, '')
	setConfig(STATE.PARAM_CHIPINFO, '')
	setConfig(STATE.PARAM_CHANNEL, '')
	setConfig(STATE.PARAM_FREQ, '')
	setConfig(STATE.PARAM_DEADLINE, '')
	setConfig(STATE.PARAM_PERIOD, '')
	setConfig(STATE.PARAM_RESULT, '')
	setConfig(STATE.PARAM_ERROR, '')
	setConfig(STATE.PARAM_RECORD_STATE, '')
	setConfig(STATE.PARAM_COUNTER, '')
	setConfig(STATE.PARAM_START_TIME, '')

def export_data(request):
	data = DwfMeasureData.objects.all()
	column_names = ['dataCounter', 'Z', 'R', 'C', 'freq', 'channel', 'time', 'timeMin']
	
	return excel.make_response_from_query_sets(data, column_names, 'xlsx', file_name="test")


# if some_queryset.filter(pk=entry.pk).exists():
def setConfig(key, value):
	queryResult = Parameter.objects.filter(key=key)
	if queryResult.exists():
		queryResult.update(value=value)
	else:
		Parameter(key=key, value=value).save()

def getConfig(key):
	queryResult = Parameter.objects.filter(key=key)
	if queryResult.exists():
		return queryResult.get(key=key).value 
	else:
		return ''

# Do not check csrf cookies for POST messages
# This function only uses collecting the data.
@csrf_exempt
def collector(request):
	result = {}
	print('Collector called')

	if request.method == 'POST':
		jsonData = json.loads(request.body)
		print(jsonData)
		menu = jsonData['menu']

		if menu == 'result':
			dataCounter = jsonData['dataCounter']
			startTime = jsonData['startTime']
			targetTime = jsonData['targetTime']
			period = jsonData['period']
			freqs = jsonData['freqs']
			channels = jsonData['channels']
			dbData = DwfResultData(dataCounter=dataCounter, startTime = startTime, 
				targetTime=targetTime, period=period, freqs=freqs, channels=channels)
			dbData.save()
			result['result'] = True
		elif menu == 'scope':
			dataCounter = jsonData['dataCounter']
			time = jsonData['time']
			timeMin = jsonData['timeMin']
			Z = jsonData['Z']
			R = jsonData['R']
			C = jsonData['C']
			freq = jsonData['freq']
			channel = jsonData['channel']
			for idx in range(len(channel)):
				dbData = DwfMeasureData(dataCounter=dataCounter, time=time, timeMin=timeMin,
					Z=Z[idx], R=R[idx], C=C[idx], freq=freq[idx], channel=channel[idx])
				dbData.save()

			result['result'] = True
		else:
			result['result'] = False

		#for i, (d0, d1, d2) in enumerate(zip(jsonData['freq'], jsonData['gain'], jsonData['phase'])):
		#	data = DwfData(time=time, freq=d0, gain=d1, phase=d2)
		#	data.save()

		# currently alway return to true
		

	return HttpResponse(json.dumps(result), content_type='application/json')

# This function get/set the parameters.
# The parameter arranged in protocol.py file.
@csrf_exempt
def state(request):
	result = {}

	if request.method == 'POST':
		jsonData = json.loads(request.body)
		menu = jsonData['menu']
		key = jsonData['key']

		if menu == 0: # set menu
			value = jsonData['value']
			result['result'] = True
			setConfig(key, value)
		elif menu == 1: # get menu
			result['result'] = True
			result['value'] = getConfig(key)
	else:
		result['result'] = False
		result['error'] = 'not supported protocol(only POST)'

	return HttpResponse(json.dumps(result), content_type='application/json')

@csrf_exempt
def init(request):
	if(request.method == 'POST'):
		# initConfig function always succeed.
		initConfig()

		return HttpResponse('{"result":true}')
	else:
		return HttpResponse('{"result":false}')

@csrf_exempt
def command(request):
	if(request.method == 'POST'):
		result = {}
		print(request.body)
		jsonData = json.loads(request.body)
		command = jsonData['command']

		# waiting 10 sec maximum
		timeout = 50
		counter = 0

		# Make sure the setup command, must be not called in progress.
		if(command == STATE.COMMAND_CHECKCHIP):
			# Clear previous chipinfo
			setConfig(STATE.PARAM_CHIPINFO, '')
			setConfig(STATE.PARAM_RESULT, '')

			# setting the parameter with setup
			setConfig(STATE.PARAM_COMMAND, STATE.COMMAND_CHECKCHIP)

			# waiting the parameter changed.
			while(True):
				time.sleep(0.2)

				res = getConfig(STATE.PARAM_RESULT)
				
				if(res == 'OK'):
					chipInfo = getConfig(STATE.PARAM_CHIPINFO)

					result['result'] = True
					result['value'] = chipInfo
					break
				elif(res == 'FAILED'):
					result['result'] = False
					result['error'] = getConfig(STATE.PARAM_ERROR)
					break

				counter = counter + 1
				if(counter == timeout):
					result['result'] = False
					result['error'] = "No device connected"
					break

			# reset the result
			setConfig(STATE.PARAM_RESULT, '')
		elif(command == STATE.COMMAND_SETUP):
			freqs = jsonData['freqs']
			period = jsonData['period']
			deadline = jsonData['deadline']
			channels = jsonData['channels']
			counter = 1

			tempCounter = DwfResultData.objects.all().aggregate(Max('dataCounter'))
			if(tempCounter['dataCounter__max'] == None):
				tempCounter = 1
			else:
				counter = int(tempCounter['dataCounter__max']) + 1

			setConfig(STATE.PARAM_RESULT, '')
			setConfig(STATE.PARAM_FREQ, freqs)
			setConfig(STATE.PARAM_PERIOD, period)
			setConfig(STATE.PARAM_DEADLINE, deadline)
			setConfig(STATE.PARAM_CHANNEL, channels)
			setConfig(STATE.PARAM_COUNTER, counter)

			setConfig(STATE.PARAM_COMMAND, STATE.COMMAND_SETUP)

			# waiting the parameter changed.
			while(True):
				time.sleep(0.2)

				res = getConfig(STATE.PARAM_RESULT)
				if(res == 'OK'):
					result['result'] = True
					break
				elif(res == 'FAILED'):
					result['result'] = False
					result['error'] = getConfig(STATE.PARAM_ERROR)
					break

				counter = counter + 1
				if(counter == timeout):
					result['result'] = False
					result['error'] = "No device connected"
					break
		elif(command == STATE.COMMAND_START):
			setConfig(STATE.PARAM_RESULT, '')
			setConfig(STATE.PARAM_COMMAND, STATE.COMMAND_START)

			print('command start received')
			# change the timeout to 20 secs
			timeout = 50*2

			# waiting the parameter changed.
			while(True):
				time.sleep(0.2)

				res = getConfig(STATE.PARAM_RESULT)
				if(res == 'OK'):
					result['result'] = True
					break
				elif(res == 'FAILED'):
					result['result'] = False
					result['error'] = getConfig(STATE.PARAM_ERROR)
					break

				counter = counter + 1
				if(counter == timeout):
					result['result'] = False
					result['error'] = "Timeout"
					break
		elif(command == STATE.COMMAND_STOP):
			setConfig(STATE.PARAM_RESULT, '')
			setConfig(STATE.PARAM_COMMAND, STATE.COMMAND_STOP)

			print('command stop received')

			timeout = 50*2

			# waiting the parameter changed.
			while(True):
				time.sleep(0.2)

				res = getConfig(STATE.PARAM_RESULT)
				if(res == 'OK'):
					initConfig()
					result['result'] = True
					break
				elif(res == 'FAILED'):
					result['result'] = False
					result['error'] = getConfig(STATE.PARAM_ERROR)
					break

				counter = counter + 1
				if(counter == timeout):
					result['result'] = False
					result['error'] = "Timeout"
					break
		elif(command == STATE.COMMAND_CHECKSTATE):
			timeFormat = '%Y-%m-%d %H:%M:%S'

			channel = getConfig(STATE.PARAM_CHANNEL)
			freq = getConfig(STATE.PARAM_FREQ)

			# change the list type
			if(channel != ""):
				channel = ast.literal_eval(channel)
				channel = ", ".join(str(x) for x in channel[:])
			if(freq != ""):
				freq = ast.literal_eval(freq)
				freq = ", ".join(str(x) for x in freq[:])

			result['result'] = True
			result["state"] = getConfig(STATE.PARAM_STATE)
			result["chipInfo"] = getConfig(STATE.PARAM_CHIPINFO)
			result["channel"] = channel
			result["freq"] = freq
			result["deadline"] = getConfig(STATE.PARAM_DEADLINE)
			result["period"] = getConfig(STATE.PARAM_PERIOD)
			result["recordState"] = getConfig(STATE.PARAM_RECORD_STATE)			
			result["startTime"] = getConfig(STATE.PARAM_START_TIME)
			if(result["startTime"] != ""):
				endTime = datetime.datetime.strptime(result["startTime"], timeFormat) + datetime.timedelta(days=int(result["deadline"]))
				print(endTime)
				result["endTime"] = endTime.strftime(timeFormat)
		elif(command == STATE.COMMAND_GET_RESULT_LIST):
			datas = DwfResultData.objects.order_by("-dataCounter")[:6]
			result["result"] = True
			result["dataCounter"] = []
			result["timeRange"] = []
			result["period"] = []
			result["freqs"] = []
			result["channels"] = []
			result["state"] = getConfig(STATE.PARAM_STATE)

			for data in datas:
				channels_value = ast.literal_eval(data.channels)
				channels_value = [x+1 for x in channels_value]

				result["dataCounter"].append(data.dataCounter)
				result["timeRange"].append(str(data.startTime) + "~<br>" + str(data.targetTime))
				result["period"].append(data.period)
				result["freqs"].append(data.freqs)
				result["channels"].append(str(channels_value)) # for viewer

			print(result)

		return HttpResponse(json.dumps(result), content_type='application/json')

	else:
		return HttpResponse('{"result":false}')

def graph(request):
	dataCounter = request.GET.get('dataCounter', '')
	channels = request.GET.get('channels', '')
	freqs = request.GET.get('freqs', '')
	dataSelection = request.GET.get('dataSelection', '')

	print "dataCounter %s, channels %s, freqs %s" % (dataCounter, channels, freqs)

	if dataCounter != '' and channels != '' and freqs != '' and dataSelection != '':
		channels = ast.literal_eval("[" + channels + "]")
		freqs = ast.literal_eval("[" + freqs + "]")
		series = []
		series_options_terms = {}

		dateTime = DwfMeasureData.objects.filter(dataCounter=dataCounter, channel=channels[0], freq=freqs[0]).values("time")
		# print dateTime.get()
		# dateTime.update("")

		for channel in channels:
			queryData = DwfMeasureData.objects.filter(dataCounter=dataCounter, channel=channel, freq__in=freqs)
			series_term = {"channel%d_%s" %(channel+1, dataSelection) : dataSelection}
			series_options_term = "channel%d_%s" %(channel+1, dataSelection)
			series.append({"options" :{
							"source" : queryData},
							"terms" : [{"channel%d_time" % (channel+1) : "timeMin"}, 
										series_term]})

			series_options_terms["channel%d_time" % (channel+1)] = [series_options_term] 
		chartData = DataPool(series=series)
		chart = Chart(
			datasource=chartData,
			series_options=
				[{"options" : {
					"type" : "line", 
					"stacking" : False},
				  "terms" : series_options_terms}],
			chart_options= {'title': {
               'text': 'Impedence Data'},
           		'xAxis': {
	                'title': {
                   		'text': 'time(min)'}},
                'yAxis': {
	                'title': {
                   		'text': 'Impedence'}}})

		return render(request, 'graph.html', {'graphData':chart})	
	return HttpResponse('')

def error(request):
	return render(request, 'error.html')

def main(request):
	return render(request, 'index.html')