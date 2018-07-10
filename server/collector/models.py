from __future__ import unicode_literals

from django.db import models

# Model for dwf 

class DwfResultData(models.Model):
	dataCounter = models.IntegerField(primary_key=True, default=0)
	startTime = models.DateTimeField(blank=True, null=True)
	targetTime = models.DateTimeField(blank=True, null=True)
	period = models.IntegerField(null=False, default=1)
	freqs = models.TextField(null=False, default='')
	channels = models.TextField(null=False, default='')

class DwfMeasureData(models.Model):
	id = models.AutoField(primary_key=True)
	dataCounter = models.IntegerField(null=False, default=0)
	Z = models.FloatField(null=False, default=0.0)
	R = models.FloatField(null=False, default=0.0)
	C = models.FloatField(null=False, default=0.0)
	freq = models.IntegerField(null=False, default=0)
	channel = models.IntegerField(null=False, default='')
	time = models.DateTimeField(blank=True, null=True)
	timeMin = models.IntegerField(null=False, default=0)

class Parameter(models.Model):
	id = models.AutoField(primary_key=True)
	key = models.TextField(null=False, default="")
	value = models.TextField(null=False, default="")
