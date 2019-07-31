
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>

#include "plcm.h"

const char *progname = "unknown";

/* Info about all the extensions, even though not many of them will be used.
*/
int fixes_event_base, fixes_error_base;
int composite_event_base, composite_error_base;
int damage_event_base, damage_error_base;

Display *disp;
Window ctrl_win;

create_trans_func_t create_trans;

int last_x_error = 0;

Atom _PLCM_CONTROL_WINDOW;
Atom _PLCM_ENABLE;
Atom _PLCM_DISABLE;
Atom _PLCM_BRIGHTNESS;

static int x_error_handler(Display *d, XErrorEvent *error);

int main(int argc, char **argv)
{
  int has_render = 0;
  glx_version_t glx_version = NO_GLX;

  int major, minor;
  XSetWindowAttributes attrs;
  
  /* FIXME: process command line args */
  
  progname = argv[0];
  
  disp = XOpenDisplay(NULL);
  if (disp == NULL)
    die("could not open display");


  /* The default error handler will terminate us, which isn't very
     nice.  Use our own instead.
  */
  XSetErrorHandler(x_error_handler);


  /* Check that all the necessary extensions are here.  Maybe we
     should check that the required minimum versions are available,
     but that has to wait until we know that the minimal might be.
  */

  if (!XFixesQueryExtension(disp, &fixes_event_base, &fixes_error_base))
    die("could not find fixes extension");

  if (!XFixesQueryVersion(disp, &major, &minor))
    die("could not get fixes version");

  info("using fixes extension %d.%d (lib %d)", major, minor, XFixesVersion());


  if (!XCompositeQueryExtension(disp, &composite_event_base, &composite_error_base))
    die("could not find composite extension");

  if (!XCompositeQueryVersion(disp, &major, &minor))
    die("could not get composite version");

  info("using composite extension %d.%d (lib %d)", major, minor, XCompositeVersion());


  if (!XDamageQueryExtension(disp, &damage_event_base, &damage_error_base))
    die("could not find damage extension");

  if (!XDamageQueryVersion(disp, &major, &minor))
    die("could not get damage version");

  info("using damage extension %d.%d", major, minor);

  has_render = check_render();
  glx_version = check_glx();

  /* Use best trans method available
   */
  if (glx_version == GLX_13)
    {
      info("WARNING: using GLX 1.3, this code is completely untested"); 
      create_trans = create_trans_glx13;
    }
  else if (has_render)
    {
      info("using RENDER extension");
      create_trans = create_trans_render;
    }
  else if (glx_version == GLX_12)
    {
      info("using GLX 1.2 (which is _slow_)");
      create_trans = create_trans_glx12;
    }
  else
    die("requires either render or glx extensions");


  /* Intern all the atoms used in the communication with plwm
   */
  _PLCM_CONTROL_WINDOW = XInternAtom(disp, "_PLCM_CONTROL_WINDOW", False);
  _PLCM_ENABLE = XInternAtom(disp, "_PLCM_ENABLE", False);
  _PLCM_DISABLE = XInternAtom(disp, "_PLCM_DISABLE", False);
  _PLCM_BRIGHTNESS = XInternAtom(disp, "_PLCM_BRIGHTNESS", False);


  /* Create a control window, which plwm sends messages to to enable
     composition.
  */
  ctrl_win = XCreateWindow(disp, RootWindow(disp, 0),
			   0, 0, 10, 10, 0, 0, InputOnly, CopyFromParent,
			   0, &attrs);
  

  /* Register rendez-vous property */
  XChangeProperty(disp, RootWindow(disp, 0),
		  _PLCM_CONTROL_WINDOW, XA_WINDOW, 32,
		  PropModeReplace, (unsigned char*) &ctrl_win, 1);


  /* Run until told to die */
  event_loop();
  

  /* Remove any redirections */
  /* Remove rendez-vous property */

  XDeleteProperty(disp, ctrl_win, _PLCM_CONTROL_WINDOW);
  XDestroyWindow(disp, ctrl_win);

  XCloseDisplay(disp);
  disp = NULL;

  return 0;
}


void info(const char *fmt, ...)
{
  char buf[2000];
  va_list args;

  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);

  fprintf(stderr, "%s: %s\n", progname, buf);
}
  

void die(const char *fmt, ...)
{
  char buf[2000];
  va_list args;

  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);

  fprintf(stderr, "%s: error: %s\n", progname, buf);
  exit(1);
}
  

static int x_error_handler(Display *d, XErrorEvent *error)
{
  char name[50];

  if (XGetErrorText(d, error->error_code, name, sizeof(name)) != Success)
    {
      sprintf(name, "X error %d", error->error_code);
    }

  info("%s for request %d minor %d resource 0x%08x",
       name, error->request_code, error->minor_code,
       (int) error->resourceid);

  last_x_error = error->error_code;
  
  return 0;
}
