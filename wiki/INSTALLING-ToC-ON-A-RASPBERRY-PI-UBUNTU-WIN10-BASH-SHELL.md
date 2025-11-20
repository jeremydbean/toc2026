**NOTE: HIGHLY recommend using Ubuntu 18.04 LTS - it seems to be the build that works the best for this.  For more modern Ubuntu, check out tocGPT - https://github.com/jeremydbean/tocGPT**

### PRE-INSTALL APP REQUIREMENTS:

Open terminal (Ctrl + Alt + T) and do the following: <br> <br>
>       sudo apt update
>       sudo apt upgrade /y
>       sudo apt-get update
>       sudo apt install csh build-essential telnet git lnav libcurl4-openssl-dev
<br>

### COPYING OVER TOC FROM GITHUB:

Open terminal<br> <br>
>       cd ~
>       sudo git clone http://www.github.com/jeremydbean/toc.git
>       cd toc
>       sudo git pull



### STARTING THE MUD:
_Note: This is assuming you have the username toc as your login.  If not, change the "toc:toc" in the command below to whatever your username is._

>       cd ~
>       sudo chown -R toc:toc toc
>       sudo chmod -R 755 toc
>       cd toc
>       cd src
>       rm *.o
>       make
>       cp merc ../area
>       cd ../area
>       ./merc 9000 &
   

<br>- NOTE: Don't forget the  **&** at the end of the command above, or the MUD will shut down if you log off!  If it still closes out when you log off/disconnect from the host - try using `nohup ./merc 9000 &`<p><p>


### TESTING THE MUD:

Open a new terminal window <br>
>       telnet localhost 9000



### WAYS TO MAKE MUD OPEN EASILY:

>       sudo nano ~/.bashrc
<br> * Scroll all the way to the bottom, hit enter a couple times, and add the following line:
>       cd /home/pi/ToC/area
<br> * Hit: Ctrl + X, Y, ENTER

* Every time you open a terminal window, you will be in the areas directory.
Simply type **./merc 9000 &** (or, hit the "Up" key and it's usually the last command used), and hit ENTER.<p><p>

NOTE: To both view the MUD log on the terminal, AND log to file, add the following command to the ~/.bashsrc file:

>       cd area
>       ./merc 9000 2>&1 | tee -a ../log/logfile_$(date '+%Y-%m-%d-%H').txt



### OTHER COMMANDS:

* ps ux : views all running processes. First number listed after pi is the 'Process ID' last line is the description.<p> 

* If you need to force kill the MUD,<br>
     Type:<br> 
>       ps ux

**The MUD looks something like:**


<table border="1" cellpadding="0">
    <tr>
        <td><font size="2"><b><u>USER</u></b><b> </b></font></td>
        <td><font size="2"><b><u>PID</u></b><b> </b></font></td>
        <td><font size="2"><b><u>%CPU</u></b><b> </b></font></td>
        <td><font size="2"><b><u>%MEM</u></b><b> </b></font></td>
        <td><font size="2"><b><u>VSZ</u></b><b> </b></font></td>
        <td><font size="2"><b><u>RSS</u></b><b> </b></font></td>
        <td><font size="2"><b><u>TTY</u></b><b> </b></font></td>
        <td><font size="2"><b><u>STAT</u></b><b> </b></font></td>
        <td><font size="2"><b><u>START</u></b><b> </b></font></td>
        <td><font size="2"><b><u>TIME</u></b><b> </b></font></td>
        <td><font size="2"><b><u>COMMAND</u></b><b> </b></font></td>
    <tr>
        <td><font size="2">pi</font></td>
        <td><font size="2"><b>1652</b></font></td>
        <td><font size="2">.07</font></td>
        <td><font size="2">1.0</font></td>
        <td><font size="2">12528</font></td>
        <td><font size="2">10024</font></td>
        <td><font size="2">pts/0</font></td>
        <td><font size="2">S</font></td>
        <td><font size="2">11:21</font></td>
        <td><font size="2">0:02</font></td>
        <td><font size="2">./merc 9000</font></td>
    </tr>
</table><p>

* Find the **PID** (the 1652 number in the example) for **COMMAND**  "./merc 9000"
     * Type: 
         `kill 1652`
     * _NOTE: The PID will be different each time, so be sure to ps ux to ensure it's the MUD you kill._



### NOTE: 
### Monit is a great app to monitor and automatically restart the MUD in the event it crashes.  More instructions on configuring this soon.

>       sudo apt-get install monit
>       sudo nano /etc/monit/conf.d/merc
<br>

Type the following in the script that opens, and save:

>       check host localhost with address 127.0.0.1
>       start program = "/bin/bash -c '/home/toc/startup.sh'" 
>       stop program = "/bin/bash -c '/home/toc/toc_kill.sh'"
>       if failed port 9000 then exec "/bin/bash -c '/home/toc/startup.sh'" 
<br>
After saving:

>       sudo monit reload
>       sudo monit validate


***
### Updating Github with changes (players, fixes, etc.)<br>
_[Confirms files changed]_<br>
>       git show
_[Adds all files changed]_<br>
>       git add * 
 _[Type change notes, save, close]_<br>
>       git commit -a  
_[Enter username/[personal access token](https://github.com/settings/tokens)]_ <br>
>       git push -u origin master


***

OLD (no longer used) Monit Config: <br>
>       sudo apt-get install monit
>       sudo nano /etc/monit/conf.d/merc
>       check process merc
>       matching "merc"
>       start program = "/home/toc/toc/startup.sh" as uid 1000
>       stop program = "/home/toc/toc_kill.sh" as uid 1000
>       if does not exist then restart

Then After saving, type:
>       sudo service monit restart
>       sudo monit -t       


