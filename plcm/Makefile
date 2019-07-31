# FIXME: this should be replaced by a configure:d makefile

CC	  = gcc
LD	  = gcc
CPPFLAGS += -I/usr/X11R6/include
CFLAGS	 += -Wall -g -O
LDFLAGS	 += -g
LIBS	 += -L/usr/X11R6/lib -lX11 -lXfixes -lXcomposite -lXdamage -lXrender -lGL

TARGET	= plcm
OBJS	= main.o events.o projection.o trans_glx.o trans_render.o
HEADERS = plcm.h

all: $(TARGET)

$(TARGET): $(OBJS)
	$(LD) $(LDFLAGS) -o $@ $^ $(LIBS)

# manual header dependency is good enough for this little hack
$(OBJS): $(HEADERS)

clean:
	rm -f $(TARGET) *.o
