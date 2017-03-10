#!/usr/bin/env python
""" Work out what trains to claim repay """
#pylint: disable=no-self-use
import datetime
import sys
import requests
import os
from requests.auth import HTTPBasicAuth

class Train(object):
    """ target groups """
    def __init__(self, date=datetime.datetime.now(), origin='CHX', destination='GLM'):
        # The username comes from the nationalrail darwin  service

        self.basic_auth = HTTPBasicAuth(os.environ["TRAIN_EMAIL"], os.environ["TRAIN_PASSWORD"])
        self.date = date

        # morning origin -> destination
        self.get_schedule(start="0630",
                          end="1000",
                          origin=origin,
                          destination=destination)
        # evening destination -> origin
        self.get_schedule(start="1730",
                          end="2200",
                          origin=destination,
                          destination=origin)

    def get_schedule(self, start="0630", end="0930", origin='WGC',
                     destination='KGX'):
        """ returns the train schedule """
        date = self.date.strftime("%Y-%m-%d")
        postdata = {"from_loc":origin, "to_loc":destination,
                    "from_time":start, "to_time":end,
                    "from_date":date, "to_date":date,
                    "days":"WEEKDAY"}
        # get all the services for the specified times
        resp = requests.post('https://hsp-prod.rockshore.net/api/v1/serviceMetrics',
                             auth=self.basic_auth,
                             json=postdata)
        if resp.status_code != 200:
            print("Ret code is not 200", resp.status_code)

        resp_data = resp.json()
        # go and get the train details
        for service in resp_data['Services']:
            self.get_train(service['serviceAttributesMetrics']['rids'][0],
                           origin, destination)

    def convert_time(self, time_string):
        """ converts the possible HH:MM to a datetime """
        if time_string == "":
            return datetime.datetime.strptime("0000", "%H%M")
        else:
            return datetime.datetime.strptime(time_string, "%H%M")

    def calc_times(self, location):
        """ returns the times with some deltas, it appears
            that sometimes they don't record valid times so make
            a best efforts guess at something
        """
        # start or end of journey
        if location['gbtt_pta'] == '' and location['actual_ta'] == '':
            location['gbtt_pta'] = '0000'
            location['actual_ta'] = '0000'
        if location['gbtt_ptd'] == '' and location['actual_td'] == '':
            location['gbtt_ptd'] = '0000'
            location['actual_td'] = '0000'

        planned_arrival = self.convert_time(location['gbtt_pta'])
        planned_departure = self.convert_time(location['gbtt_ptd'])
        actual_arrival = self.convert_time(location['actual_ta'])
        actual_departure = self.convert_time(location['actual_td'])
        arrival_lateness = actual_arrival - planned_arrival
        departure_lateness = actual_departure - planned_departure

        return {'planned_arrival':planned_arrival,
                'planned_departure': planned_departure,
                'actual_arrival': actual_arrival,
                'actual_departure': actual_departure,
                'arrival_lateness': arrival_lateness,
                'departure_lateness': departure_lateness}

    def late_or_early(self, delta):
        """ early or late time """
        if delta.total_seconds() < 0:
            return (-delta, "early")
        else:
            return (delta, "late")

    def get_train(self, rid, origin, destination):
        """ gathers and prints data about a specific train """
        postdata = {"rid" : rid}
        resp = requests.post('https://hsp-prod.rockshore.net/api/v1/serviceDetails',
                             auth=self.basic_auth,
                             json=postdata)
        if resp.status_code != 200:
            print("Ret code is not 200 - ", resp.status_code)
            return

        resp_data = resp.json()
        journey = {}
        journey['origin'] = origin
        journey['destination'] = destination
        for location in resp_data['serviceAttributesDetails']['locations']:

            if location['location'] == destination:
                times = self.calc_times(location)
                journey['actual_arrival'] = times['actual_arrival']
                (journey['arrival_lateness'],
                 journey['arrival_el']) = self.late_or_early(times['arrival_lateness'])
                journey['code'] = location['late_canc_reason']

            if location['location'] == origin:
                times = self.calc_times(location)
                journey['planned_departure'] = times['planned_departure']
                journey['actual_departure'] = times['actual_departure']
                (journey['departure_lateness'],
                 journey['departure_el']) = self.late_or_early(times['departure_lateness'])

        self.print_journey(journey)

    def print_journey(self, journey):
        """ print out the journey information """
        if journey['code'] == "":
            code = ""
        else:
            code = "(%s)" % (journey['code'])
        # 15 minutes and we can claim!
        if journey['arrival_lateness'].total_seconds() > 1800 or journey['actual_departure'].strftime("%H:%M") == "00:00":
            claim = "Claim"
        else:
            claim = ""
        print("%s %s %s to %s departed %s (%s %s), arrived %s (%s %s) %s %s" % (
            self.date.strftime("%Y-%m-%d"),
            journey['planned_departure'].strftime("%H:%M"),
            journey['origin'],
            journey['destination'],
            journey['actual_departure'].strftime("%H:%M"),
            journey['departure_lateness'],
            journey['departure_el'],
            journey['actual_arrival'].strftime("%H:%M"),
            journey['arrival_lateness'],
            journey['arrival_el'],
            code,
            claim,
            ))


#Train(origin=sys.argv[1], destination=sys.argv[2])
Train(origin=os.environ["TRAIN_ORIGIN"], destination=os.environ["TRAIN_DESTINATION"])
