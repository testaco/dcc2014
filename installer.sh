#!/usr/bin/sh
apt-get install python git-core python-virtualenv python-pip
git clone https://github.com/testaco/dcc2014.git
cd dcc2014
virtualenv env
source env/bin/activate
pip install numpy matplotlib scipy myhdl
