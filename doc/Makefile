
default: info

all: info ps html

info: plwm.info

ps: plwm.ps

pdf: plwm.pdf

html: plwm_toc.html

clean:
	rm -f *.{info,ps,html,aux,cp,fn,fns,ky,log,pg,toc,tp,vr,vrs}

%.info: %.texi
	makeinfo --no-split $<

%.dvi: %.texi
	texi2dvi $<
        # Run it twice to catch new cross-references
	texi2dvi $<

%.ps: %.dvi
	dvips -o $@ $<

%.pdf: %.dvi
	dvipdfm -o $@ $<

%_toc.html: %.texi
	texi2html -split_node $<
