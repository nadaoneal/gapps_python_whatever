#!/usr/bin/python
#===============================================================================
#
# Will empty out the events from calendars whose titles are in a set you create, or that match a given regex.
# The account you're logging in to needs to own the calendars.
#
#===============================================================================

import time
import string
import subprocess
from subprocess import Popen, PIPE, STDOUT
import sys
import re

import atom
import gdata.data
import gdata.apps.service
import gdata.calendar.service
import gdata.calendar_resource.client

## Google Apps Clients/Services Connections ##

def openGoogleCalendarService(loginEmail, loginPass, googleSource):
    # open Calendar Service connection
    calendar_service = gdata.calendar.service.CalendarService()
    calendar_service.email = loginEmail
    calendar_service.password = loginPass
    calendar_service.source = googleSource
    calendar_service.ProgrammaticLogin()
    return calendar_service
# end def OpenGoogleCalendarService()

def getMatchingCalIDs(calendar_service, calsToEmpty, calsPatternToEmpty):
    def returnEmailOnCal(calendar):
        tmp = calendar.id.text.replace("%40","@").replace("http://www.google.com/calendar/feeds/default/allcalendars/full/","")
        return tmp
    # end def returnEmailOnCal()
    
    def isACalToEmpty(item):
        debug = True
        if item.title is not None and \
                (item.title.text in calsToEmpty or \
                 re.search(calsPatternToEmpty, item.title.text)) : 
            if debug:
                print "going to empty " + item.title.text
            return True
        else:
            return False
    # end def matchCalsToEmpty()
    
    # now get the calsFeed and do a list comprehension
    calsFeed = calendar_service.GetAllCalendarsFeed()
    return [returnEmailOnCal(x) for x in calsFeed.entry if isACalToEmpty(x)] 
# end def getMatchingCalIDs()

def main():
    # domain/login details...
    loginEmail = 'USER@domain'
    loginPass = 'PASSWORD'
    loginDomain = 'DOMAIN'
    googleSource = loginDomain + '.empty.calendars'
    debug = True
  
    # logging details
    todaysDate = time.strftime('%Y-%m-%d')
    logSaveFile = todaysDate + "/00-log.txt"

    # which calendars do you want to empty?
    # calsPattern and calsToEmpty match on the calendar title
    # kludge: set the pattern to something impossible to just use the set; 
    #     make the set empty, or contain pattern matches only, to just use the pattern
    calsPatternToEmpty = "^[0-9]*EO?$"
    calsToEmpty = frozenset(['2462E', '2462EO', '2463E', '2463EO', '2464E', \
                                  '2464EO', '2465E', '2465EO', '2377E', '2377EO'])

    # what date range should be emptied?
    # sorry, this is required
    # Also NOTE: if you have more than 9999 events, you will need to run this program more than once
    start_date = "2008-01-01"
    end_date = "2012-12-31"

    # send all stdout and stderr to the log (unless debug)
    if not debug:
        # open the log file
        # dude, this seriously needs try/catch
        # why was I born so lazy?
        subprocess.call(['mkdir', todaysDate])
        subprocess.call(['touch', logSaveFile])
        logOut = open(logSaveFile, 'a')
        sys.stdout = logOut
        sys.stderr = logOut
    
    # start timer
    timeStart = time.time()
    print "Started at " + time.strftime('%Y-%m-%d %H:%M')
    
    # open calendar and contacts services
    calendar_service = openGoogleCalendarService(loginEmail, loginPass, googleSource)
    
    # get listing of calendar objects for calendars you want to empty
    matchingCalIDs = getMatchingCalIDs(calendar_service, calsToEmpty, calsPatternToEmpty)
    
    # for each calendar, get a listing of events, and delete all of them

    for calID in matchingCalIDs:
        # get feed of current events from the calendar
        if debug:
            print "In Calendar " + calID
        query = gdata.calendar.service.CalendarEventQuery(calID, 'private', 'full')
        query.start_min = start_date
        query.start_max = end_date 
        query.max_results = 9999
        try:
            feed = calendar_service.CalendarQuery(query)
        except gdata.service.RequestError, e:
            print "failed first attempt to get event list of" + calendar.title.text
            print e
            sleep(20)
            try:
                feed = calendar_service.CalendarQuery(query)
            except gdata.service.RequestError, e:
                print "giving up on " + calendar.title.text
                print e
                return False
    
        # now iterate over the feed and delete each event
        # could also chunk this into several batch requests, viz:
        # http://code.google.com/apis/calendar/data/1.0/developers_guide_python.html#batch
        for event in feed.entry:
            if debug:
                print "Deleting " + event.content.text.rstrip()
            calendar_service.DeleteEvent(event.GetEditLink().href)

    
    #### clean up...
    totalSecondsElapsed = time.time() - timeStart
    hoursElapsed = int(totalSecondsElapsed / 3600)
    minutesElapsed = int((totalSecondsElapsed - hoursElapsed*3600) / 60)
    print "Total time: %s hours, %s minutes (%s total seconds)\n\n" % (hoursElapsed, minutesElapsed, totalSecondsElapsed)
    if not debug:
        logOut.close()
    

# end def of main()

if __name__ == '__main__':
  main()