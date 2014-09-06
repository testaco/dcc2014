all: part1 part2 part3 part4

part1: plots code
	pdflatex DCC2014-1.latex

part2: plots code
	pdflatex DCC2014-2.latex

part3: plots code
	pdflatex DCC2014-3.latex

part4: plots code
	pdflatex DCC2014-4.latex

plots:
	make -C img

code:
	make -C code

clean:
	rm -f *.nav *.log *.aux *.snm *.toc *.out *.pdf *.vrb
