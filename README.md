# GetGrass Auto Farmer
GetGrass.io Auto Farmer | Automate Farming Grass use Python and Proxies.
## Tools and components required
1. GetGrass.io Account UserID | Register: [https://app.getgrass.io](https://app.getgrass.io/register/?referralCode=PnmuSjrqxyxvZsk)
2. Proxies
3. VPS or RDP (OPTIONAL)
4. Python version 3.10 or Latest
### Buy Proxies
- Free Proxies Static Residental: 
1. [WebShare](https://www.webshare.io/?referral_code=p7k7whpdu2jg)
2. [ProxyScrape](https://proxyscrape.com/?ref=odk1mmj)
3. [MonoSans](https://github.com/monosans/proxy-list)
- Paid Premium Static Residental:
1. [922proxy](https://www.922proxy.com/register?inviter_code=d03d4fed)
2. [Proxy-Cheap](https://app.proxy-cheap.com/r/JysUiH)
3. [Infatica](https://dashboard.infatica.io/aff.php?aff=544)
### Get Grass UserID
- Login to https://app.getgrass.io
- Press f12 go to console, then type ```allow pasting``` insert to console
![0001](https://github.com/im-hanzou/getgrass_bot/blob/main/pasting.JPG)
- Then insert this code to console
```localStorage.getItem('userId')```
![0001](https://github.com/im-hanzou/getgrass_bot/blob/main/userid.JPG)
- Copy the code without ``'`` or ``"``
## Installation
- Install Python For Windows: [Python](https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe)
- For Unix:
```bash
apt install python3 python3-pip git -y
```
- For Termux:
```bash
pkg install python python-pip git -y
```
- Download script [Manually](https://github.com/im-hanzou/getgrass/archive/refs/heads/main.zip) or use git:
```bash
git clone https://github.com/im-hanzou/getgrass
```
- Make sure you already in bot folder:
```bash
cd getgrass
```
- Install requirements, Windows and Termux:
```bash
pip install -r requirements.txt
```
- Unix:
```bash
pip3 install -r requirements.txt
```
## Run the Bot
- Replace the proxies ```proxy_list.txt``` to your own proxies, the format is like:
```bash
protocol://127.0.0.1:8080
protocol://user:pass@127.0.0.1:8080
```
- Windows and Termux:
```bash
python run.py
```
- Unix:
```bash
python3 run.py
```
>Then insert your grass acount UserID
# Notes
- Run this bot, use my referrer code if you don't have one.
- You can just run this bot at your own risk, I'm not responsible for any loss or damage caused by this bot.
- This bot is for educational purposes only.
