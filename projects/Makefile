pys = bus.py cpu.py dsp.py mem.py soc.py system.py

all: project1 project2 project3

project1: project1.py $(pys)
	python project1.py

project2: project2.py $(pys)
	python project2.py

project3: project3.py $(pys)
	python project3.py

clean:
	rm -f *.vcd* *.v *.pyc *.png *.latex
