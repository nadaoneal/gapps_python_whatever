#!/usr/local/bin/python
#===============================================================================
# listsub.py: list everyone who has subscribed to a FundCodes calendar
# then email some people about it
# Please note that the script should be improved by 
#    (a) using oath to authenticate to the users' acocunts
#    (b) using Google's API to list user subscriptions - must be doable somehow
#===============================================================================

import time
import string
import random
import subprocess
import sys

import mechanize
from pyparsing import makeHTMLTags,SkipTo

import gdata.apps.service

import smtplib
from email.mime.text import MIMEText

# getUserCal gets html that includes all the user's subscriptions. This is pretty silly. 
# There should be some kind of API function.
def getUserCal(userName, br, samlResponse, todaysDate):
     samlResponseText = samlResponse.read()
     theStart,theEnd = makeHTMLTags("textarea")
     search = theStart + SkipTo(theEnd)("body")+ theEnd
             
     saml_resp_str = search.searchString(samlResponseText)[0].body
     relay_state_str = search.searchString(samlResponseText)[1].body
     
     fileNametoSave = todaysDate + "/" + userName + ".html"
     
     br.select_form(name="acsForm")
     br["SAMLResponse"] = saml_resp_str
     br["RelayState"] = relay_state_str
     try: 
         br.submit()
     except:
         print "WARN: trouble downloading cal data for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
         time.sleep(60)
         try:
             br.submit()
         except:
             print "FAIL: can't get cal data for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
         else:
             print "OKAY - second try - retrieving cal data for user " + userName + " at " + time.strftime('%H:%M') + ".\n"
             br.retrieve('https://www.google.com/calendar/b/0/render',fileNametoSave)   
     else:
         print "Retrieving cal data for user " + userName + " at " + time.strftime('%H:%M') + ".\n"
         br.retrieve('https://www.google.com/calendar/b/0/render',fileNametoSave)
###### end def getUserCal

# connectAndDownload handles the http connection nonsense
def connectAndDownload(usersList, todaysDate, randomPassword):
    for a_user in (usersList):
        userName = a_user.title.text
        br=mechanize.Browser()
        try:
            br.open('YOUR LOGIN PAGE')
        except:
            print "WARN: Trouble with initial connect for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            time.sleep(60)
            try:
                br.open('YOUR LOGIN PAGE')
            except:
                print "FAIL: gave up on initial connect for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
                break
            
        br.select_form(name="theform")
        br['username']=userName
        br['password']=randomPassword
        
        # get SAML login response
        try:
            samlResponse = br.submit()
        except:
            print "WARN: can't get past SAML for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            time.sleep(60)
            try:
                samlResponse = br.submit()
            except:
                print "FAIL: can't get past SAML for " + userName + ": " +  " at " + time.strftime('%H:%M') + ".\n"
            else:
                print "OKAY: Login succeeded (second time) for " + userName + " at " + time.strftime('%H:%M') + ".\n"
                getUserCal(userName, br, samlResponse, todaysDate) 
        else:
            print "Login succeeded for " + userName + " at " + time.strftime('%H:%M') + ".\n"
            getUserCal(userName, br, samlResponse, todaysDate)
###### end def connectAndDownload

def main():
    #===============================================================================
    # ### Settings ###
    #===============================================================================
    
    # skipNames: tech people, former employees, and service accounts - we don't care about them
    skipNames = frozenset(['xxxx', 'xxxxx'])
    
    # logging, basics
    todaysDate = time.strftime('%Y-%m-%d')
    logSaveFile = todaysDate + "/00-log.txt"
    subprocess.call(['mkdir', todaysDate])
    subprocess.call(['touch', logSaveFile])
    logOut = open(logSaveFile, 'a')
    sys.stdout = logOut
    sys.stderr = logOut
    
    # google settings...
    loginEmail = 'xxx@DOMAIN'
    loginPass = 'SOMEPASS'
    loginDomain = 'DOMAIN'
    googleSource = loginDomain + ".subscription.check.script"

    # using this to bypass the users' passwords
    scpHtpasswdTo = 'USER@HOST:/PATH/.htpasswd'
    
    # grep the downloaded html files for subscriptions
    grepCommand = 'cd ' + todaysDate + '; grep -H -e [0-9][0-9][0-9][0-9]E * | cut -f 1 -d "."; cd ..'
    
    # lookup command for getting names from the userids
    lookupCommandPt1 = 'ssh USER@HOST \'lookup '
    lookupCommandPt2 = '\' | grep Name | cut -c 12-'
    
    # email settings for the message that goes out with a list of subscribers
    emailMsg = "Here's the latest list of people subscribed to at least one fund calendar. This is an automated message.\n\n"
    msgFrom = "email@domain.com"
    msgTo = "email@domain.com,email@domain.com"
    msg = MIMEText(emailMsg)
    msg['Subject'] = "Fundcode Calendar Subscribers"
    msg['From'] = msgFrom
    msg['To'] = msgTo

    # start timer
    timeStart = time.time()
    print "Started at " + time.strftime('%Y-%m-%d %H:%M') + "\n"
    
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
    
    #===============================================================================
    # For each user, set htpasswd to tonight's random password
    # BETTER SOLUTION: use oauth here
    #===============================================================================
    
    # get current .htpasswd file from server
    subprocess.call(['scp', scpHtpasswdTo, '.htpasswd'], stdout=logOut, stderr=logOut)
    
    # make a random password between 12 and 16 chars
    randMin = 12
    randMax = 16
    # note: issue: using random.sample means every character in the password is unique
    randomPassword = "".join(random.sample(string.letters+string.digits,random.randint(randMin,randMax)))
    
    # set new password for each user
    for a_user in (usersList):
        subprocess.call(["htpasswd", "-b", ".htpasswd", a_user.title.text, randomPassword], stdout=logOut, stderr=logOut)
        
    # upload back to server    
    subprocess.call(['scp', '.htpasswd', scpHtpasswdTo], stdout=logOut, stderr=logOut)
     
    #===============================================================================
    # Okay, now get a page of everything every user is subscribed to
    # BETTER: use API to get this list
    #===============================================================================

    connectAndDownload(usersList, todaysDate, randomPassword)

    #===============================================================================    
    # now grep the HTML files for the list of subscriptions
    # and email results to interested parties
    #===============================================================================
    results = subprocess.check_output(grepCommand, shell=True, stderr=subprocess.STDOUT)
    for i, uni in enumerate(results.splitlines()):
        lookupUNI = lookupCommandPt1 + uni + lookupCommandPt2
        name = subprocess.check_output(lookupUNI, shell=True, stderr=subprocess.STDOUT)
        emailMsg += '%s. %s: %s\n' % (i+1, uni, name.strip())
    # for log
    print '%s. %s: %s\n' % (i+1, uni, name.strip())
        
    s = smtplib.SMTP('localhost')
    s.sendmail(msgFrom, [msgTo], msg.as_string())
    s.quit()

    #===============================================================================
    #  clean up....
    #===============================================================================
    totalSecondsElapsed = time.time() - timeStart
    hoursElapsed = int(totalSecondsElapsed / 3600)
    minutesElapsed = int((totalSecondsElapsed - hoursElapsed*3600) / 60)
    print 'Total time: %s hours, %s minutes (%s total seconds)' % (hoursElapsed, minutesElapsed, totalSecondsElapsed)

    logOut.close()
# end def of main()

if __name__ == '__main__':
    main()
