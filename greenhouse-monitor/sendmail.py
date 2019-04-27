import os

def sendmail(subject, message):
    FROM="monitor@GreenHouse"
    TO="root"
    message = """\
From: %s
To: %s
Subject: %s

%s
""" % (FROM, TO, subject, message)
    p = os.popen("/usr/sbin/sendmail -t -i", "w")
    p.write(message)
    status = p.close()
    if status != 0:
        print("Sendmail exit status" + str(status))