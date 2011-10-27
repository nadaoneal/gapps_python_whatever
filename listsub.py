#!/usr/local/bin/python
#===============================================================================
# listsub.py: 
# list everyone who has subscribed to a calendar that looks like a fundcode
# (title is nnnnE or nnnnEO)
# then email some people about it
#===============================================================================

import time
from datetime import datetime, timedelta
import string
import subprocess
import sys
import os
import re

from ConfigParser import SafeConfigParser

import gdata.apps.service
import gdata.calendar.client

import smtplib
from email.mime.text import MIMEText

def main():
    #===============================================================================
    # ### Settings ###
    #===============================================================================
    
    # skipNames: tech people, former employees, and service accounts - we don't care about them
    skipNames = frozenset(['_backup', 'nco2104', 'jbw2137', 'eo33', 'pr339', '_sc_api', '_sc_api2', 'presentation_cul_user', 'cul', 'cornell'])
    
    # get settings from external file
    config_file = 'settings.ini'
    parser = SafeConfigParser()
    parser.read(config_file)

    # set working directory
    # take default from settings or set something here
    #baseDir = parser.get('settings', 'baseDir')
    baseDir = "/opt/pytest"
    os.chdir(baseDir)
    
    # logging, basics
    todaysDate = time.strftime('%Y-%m-%d')
    logSaveFile = todaysDate + "-fundcodes-subscribers.txt"
    subprocess.call(['touch', logSaveFile])
    logOut = open(logSaveFile, 'a')
    sys.stdout = logOut
    sys.stderr = logOut
    
    # login info for non-oauth apis like provisioning...
    loginUser = parser.get('settings', 'loginUser')
    loginPass = parser.get('settings', 'loginPass')
    loginDomain = parser.get('settings', 'loginDomain')
    loginEmail = loginUser + '@' + loginDomain
    loginURL = 'http://' + loginDomain

    # oath stuff
    consumerKey = loginDomain
    consumerSecret = parser.get('settings', 'oauth_secret')

    # add googleSource
    googleSource = loginDomain + ".list.fund.subscribers.script"

    
    # email settings for the message that goes out with a list of subscribers
    emailMsg = "Here's the latest list of people subscribed to at least one fund calendar. This is an automated message.\n\n"
    msgFrom = "nco2104@columbia.edu"
    msgTo = "nco2104@columbia.edu"
    msgSubject = "Fundcode Calendar Subscribers"

    # start timer
    timeStart = datetime.now()
    print "Started at " + timeStart.strftime("%Y-%m-%d %H:%M:%S") + "\n"
    
    #===============================================================================
    # Get current list of users from Google
    #===============================================================================
    
    # login info
    gapps_service = gdata.apps.service.AppsService()
    gapps_service.email = loginEmail
    gapps_service.password = loginPass
    gapps_service.domain = loginDomain
    gapps_service.ProgrammaticLogin()
    
    # retrieve a list of all users
    userFeed = gapps_service.RetrieveAllUsers()
    
    # filter out suspended users and the skipNames
    def filterUsers(googleFeedEntry):
        if googleFeedEntry.login.suspended == "false" and googleFeedEntry.title.text not in skipNames: 
            return True
        else:
            return False
    usersList = filter(filterUsers,userFeed.entry)
    usersList.sort(key=lambda entry: entry.name.family_name)
    
    #===============================================================================
    # for each user in list, get list of all calendars. 
    # If one of them is a fund code calendar, then the user is a match.
    # Add the user to the email list; increment the number of subscribers
    #===============================================================================
    
    totalSubscribers = 0
    for googleUser in (usersList):
        googleEmail = googleUser.title.text + '@' + loginDomain
        subscribedCals = []
        calendar_client = gdata.calendar.client.CalendarClient(googleSource)
        calendar_client.auth_token = gdata.gauth.TwoLeggedOAuthHmacToken(consumerKey, consumerSecret, googleEmail)
        feed = calendar_client.GetAllCalendarsFeed()
        
        # for each calendar, check if it looks like a fund code
        for a_calendar in (feed.entry):
            if a_calendar.title is not None and re.search("^[0-9]*EO?$", a_calendar.title.text):
                subscribedCals.append(a_calendar.title.text)

        # if they're subscribed to at least one, increment totalSubscribers and append line to email message
        if len(subscribedCals) > 0:
            subscribedCals.sort()
            totalSubscribers += 1
            fullName = googleUser.name.given_name + " " + googleUser.name.family_name
            emailMsg += '%s. %s: %s \n\t(%s)\n' % (totalSubscribers, googleUser.title.text, fullName, ", ".join(subscribedCals))
          
    #===============================================================================
    #  Append total to subject and send message...
    #===============================================================================

    print emailMsg

    msg = MIMEText(emailMsg)
    msg['Subject'] = msgSubject + " (%s total)" % (totalSubscribers)
    msg['From'] = msgFrom
    msg['To'] = msgTo

    s = smtplib.SMTP('localhost')
    s.sendmail(msgFrom, [msgTo], msg.as_string())
    s.quit()

    #===============================================================================
    #  clean up....
    #===============================================================================
    timeEnd = datetime.now()
    timeElapsed = timeEnd - timeStart
    hoursElapsed = int(timeElapsed.seconds / 3600)
    minutesElapsed = int((timeElapsed.seconds - hoursElapsed*3600) / 60)
    print "Ended at " + timeEnd.strftime("%Y-%m-%d %H:%M:%S") + "\n"
    print 'Total time: %s hours, %s minutes (%s total seconds)' % (hoursElapsed, minutesElapsed, timeElapsed.seconds)

    logOut.close()
# end def of main()

if __name__ == '__main__':
    main()