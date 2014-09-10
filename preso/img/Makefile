all: exampleplt.png fourierplt.png project1-resource-tree.latex project2-resource-tree.latex project3-resource-tree.latex test_project2.png fir.png test_project3.png

project1:
	make -C ../../projects project1

project2:
	make -C ../../projects project2

project3:
	make -C ../../projects project3

project1-resource-tree.latex: project1
	cp ../../projects/project1-resource-tree.latex .

project2-resource-tree.latex: project2
	cp ../../projects/project2-resource-tree.latex .

test_project2.png: project2
	cp ../../projects/test_project2.png .

test_project3.png: project3
	cp ../../projects/test_project3.png .

project3-resource-tree.latex: project3
	cp ../../projects/project3-resource-tree.latex .

exampleplt.png: exampleplt.py
	python exampleplt.py

fourierplt.png: fourierplt.py
	python fourierplt.py

fir.png: fir.py
	python fir.py
