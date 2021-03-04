#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import re
import sys
import datetime as dt

__author__ = "Gerlando Lo Savio"
__copyright__ = "Copyright 2021 Gerlando Lo Savio"
__license__ = "LGPL"
__date__ = "2021-03-04"
__version__ = 1.3

###################################################################
# DEFAULT CONFIGURATION
# This configuration will be overridden by command line arguments
###################################################################
def_logfile = "/var/log/bigbluebutton/bbb-web.log"
def_output_basename = "bbb-report"
# Default date is today
def_date = dt.date.today().strftime("%Y-%m-%d")
# Empty strings for room and user mean "any room" and "any user"
def_room = ""
def_user = ""

###################################################################
#FUNCTIONS
###################################################################
def gen_outfile_name(req_date, req_room, req_user):
    """gen_outfile_name: Generate a string to use as a file name for the CSV
    report file, based on criteria specified by the user, if any.
    """
    basename = def_output_basename
    ext = ".csv"
    # append user specified criteria to file name
    for item in req_date, req_room, req_user:
        if item != "":
            basename = basename + "-" + item
    filename = basename + ext
    return filename

def get_user_input(date, room, user, logfile, outfile):
    """get_user_input: Read arguments from command line, and set defaults if
    any parameter is missing.
    Returns a list of parameters for subsequent processing.
    """
    desc = """Extract logs start and stop events for rooms and join and left
    events for users from BigBlueButton log. Can filter events based on date,
    room name, and user name.
    """
    epilog="""Without any option outputs all events occurred in the current day
    from default log file. Since log files are often rotated, you may need to
    specify which one to use.

    Results are put in a CSV file, by default beginning with "bbb-report".
    Columns output: Date,Time,Room,User,Event
    """
    parser = argparse.ArgumentParser(
                description=desc, epilog=epilog)
    parser.add_argument("date", type=str, nargs='?', default=date,
                help="date of the events to extract, written like {} (default is today)".format(date))
    parser.add_argument("-r", "--room", type=str, default=room,
                help="room to search for")
    parser.add_argument("-u", "--user", type=str, default=user,
                help="user to search for")
    parser.add_argument("-l", "--logfile", type=str, default=logfile,
                help="log file to parse, default is {}".format(logfile))
    parser.add_argument("-o", "--outfile", type=str, default=outfile,
                help="output file to save parsed data, default is '{}-...'".format(outfile))
    args = parser.parse_args()

    if args.outfile == outfile:
        req_outfile = gen_outfile_name(args.date, args.room, args.user)
        print("User didn't provided any output file name, data will be saved to {}".format(req_outfile))
    else:
        req_outfile = args.outfile

    return args.date, args.room, args.user, args.logfile, req_outfile

def read_data(logfile):
    """read_data: Read logfile and collect lines related to meeting start/end and
    user join/left events. Return a list of lines matching the events (or even an
    empty list, if there were no events in the supplied logfile).
    """
    # Regex to match relevant log lines including start, end, join and left events
    pattern = ".*(user_joined_message|user_left_message|meeting_started|meeting_ended).*"
    line_regex = re.compile(pattern)

    # Read lines from log and put matching ones in raw_attendance list
    with open(logfile, "r") as log:
        raw_attendance = []
        for line in log:
            if (line_regex.search(line)):
                raw_attendance.append(line)
    log.close()
    # return a list of strings including the matching lines (or an empty list,
    # if there no start, end, join and left events in the logfile)
    return raw_attendance

def parse_data(raw_attendance):
    """parse_data: Parse each item of raw_attendance, and return a list of dicts
    including: Date, Time, Room, User affected (if applicable) and Event recorded
    """
    ## Event data is in a JSON object. Compile a regular expression to extract it
    pattern = re.compile('data=(.*)')
    parsed_attendance = []
    for line in raw_attendance:
        # extract timestamps
        try:
            timestamp = dt.datetime.fromisoformat(line[0:29])
        except AttributeError:
            # required for python3 < 3.7 compatibility
            timestamp = iso8601.parse_date(line[0:29])
        # We use dates in ISO 8601 format i.e. YYYY-MM-DD
        evdate = timestamp.strftime('%Y-%m-%d')
        evtime = timestamp.strftime('%H:%M')
        # Search and extract json data from line
        payload = pattern.search(line).group(1)
        data = json.loads(payload)
        # get required details for each event
        evroom = data['name']
        event = data['description']
        # get username, of the user joing (or leaving) the meeeting, while
        # meeting start and end events aren't related to any specific user
        if data['logCode'] == "user_joined_message" or data['logCode'] == "user_left_message":
            evuser = data['username']
        elif data['logCode'] == "meeting_started" or data['logCode'] == "meeting_ended":
            evuser = ""

        record = {'Date': evdate, 'Time': evtime, "Room": evroom, "User": evuser, "Event": event}
        parsed_attendance.append(record)

    # return a list of dicts including date, time, room, user (if applicable) and event
    return parsed_attendance


###################################################################
# MAIN
###################################################################
if __name__ == '__main__':
    # Check current python version and requirements
    py_version = sys.version_info
    if py_version[0] != 3:
        print("Sorry, this program requires Python 3")
        sys.exit(1)
    elif py_version[1] < 7:
        # Python < 3.7 doesn't provide datetime.datetime.fromisoformat(),
        # this is why we need the iso8601 module
        try:
            import iso8601
        except:
            print("With Python < 3.7, this program requires  'iso8601' module.")
            print("Please install it with `pip3 install iso8601` or `apt install python3-iso8601`")
            sys.exit(1)

    # Get user input, or use defaults if missing
    req_date, req_room, req_user, logfile, outfile = get_user_input(
                                    def_date, def_room, def_user,
                                    def_logfile, def_output_basename)

    # Read events from logfile. Warn the user if logfile couldn't be found, or
    # if there were no events to parse and then exit
    try:
        raw_attendance = read_data(logfile)
    except FileNotFoundError:
        print("Sorry, can't find {} - try a different log file!".format(logfile))
        sys.exit(2)
    else:
        if len(raw_attendance) == 0:
            print("Sorry, no events found, try a different log file.")
            sys.exit(3)

    # Parse lines from log file, and convert them in a list of dicts with the data
    parsed_attendance = parse_data(raw_attendance)
