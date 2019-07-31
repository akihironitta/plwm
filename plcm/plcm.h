
#ifndef __PLCM_H_INCLUDED__
#define __PLCM_H_INCLUDED__

/* We need a lot of X magic */
#define GLX_GLXEXT_PROTOTYPES

#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/extensions/Xfixes.h>
#include <X11/extensions/Xcomposite.h>
#include <X11/extensions/Xdamage.h>

/* "API" for the control interface presented by plcm */

/* Property put on root window of screen 0, informing plwm about the
   window it should send ClientMessages too to enable or disable
   composition of certain windows.
*/
extern Atom _PLCM_CONTROL_WINDOW;


/* ClientMessage type for enabling rendering of a window.  Takes two
   32-bit arguments:
     source window
     target window

   The source window should already have been redirected in manual
   update mode by the caller.

   A single source window can (for now) only be mapped to a single
   target window.
 */
extern Atom _PLCM_ENABLE;


/* ClientMessage type for disabling composition of a window.  Takes two
   32-bit arguments:
     source window
     target window
 */
extern Atom _PLCM_DISABLE;


/* Property set on the target window to control the brightness.
   Type:   INTEGER
   Format: 32
   Value:  brightness

   The range is -255 (black) to +255 (white).
*/
extern Atom _PLCM_BRIGHTNESS;


typedef struct trans_base_s trans_base_t;

/* Single-linked list of managed source windows projected onto a
   target window.  Not the fastest way to keep track of them, but at a
   given time probably only a few windows will be handled, and of them
   the bulk of the processing time will be rendering and not
   traversing this list.
 */
typedef struct projection_s
{
  struct projection_s *next;

  Window source_window;
  Window target_window;

  Window root;
  Screen *screen;
  Visual *visual;
  GC gc;

  int target_is_visible;
  int target_width;
  int target_height;
  
  int source_is_mapped;
  XRectangle source_geometry;

  /* Track when source redraws itself */
  Damage damage;
  XserverRegion damage_region;

  /* Current projection settings */
  int brightness;

  /* Pixel trans implementation object */
  trans_base_t *trans;
  
} projection_t;


/* Pixels can be transferred and transformed from the source window to
   the target window using different methods, each with their
   advantages and disadvantages.

   The actual method is hidden by this C-style OO abstraction.
*/

/* Trans objects interface */

/* Destroy the trans object */
typedef void (*trans_destroy_func_t)(trans_base_t *trans);

/* Transfer and transform source pixels in the rectangle to the target
   window.
 */
typedef void (*trans_rectangle_func_t)(trans_base_t *trans, XRectangle *rect);


/* Optional: react to target window size changes.
 */
typedef void (*trans_target_resized_func_t)(trans_base_t *trans);

typedef struct trans_ops_s
{
  trans_destroy_func_t destroy;
  trans_rectangle_func_t trans_rectangle;
  trans_target_resized_func_t target_resized; /* Can be NULL */
} trans_ops_t;

/* Base for all trans objects, they must define their own struct with
   this struct as the first member.  (Typedefed above)
*/
struct trans_base_s
{
  trans_ops_t *ops;
  projection_t *proj;
};

/* Given a new projection, return a trans object.  The function must
   set all members in the base object.
 */
typedef trans_base_t* (*create_trans_func_t)(projection_t *proj);


typedef enum {
  NO_GLX,
  GLX_12,
  GLX_13
} glx_version_t;


extern const char *progname;

/* Info about all the extensions, even though not many of them will be used.
*/
extern int fixes_event_base, fixes_error_base;
extern int composite_event_base, composite_error_base;
extern int damage_event_base, damage_error_base;

extern Display *disp;
extern Window ctrl_win;

extern create_trans_func_t create_trans;

extern int last_x_error;

void info(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void die(const char *fmt, ...) __attribute__((format(printf, 1, 2), noreturn));

void event_loop(void);

/* Trans implementations */
int check_render();
trans_base_t* create_trans_render(projection_t *proj);

glx_version_t check_glx();
trans_base_t* create_trans_glx12(projection_t *proj);
trans_base_t* create_trans_glx13(projection_t *proj);


/* Add a projection for source -> target, setting up all necessary
   resources and requesting the composition redirection.
 */
projection_t* add_projection(Window source, Window target);

/* Remove a projection, releasing all resources associated with it.
 */
void free_projection(projection_t *proj);

/* Look up a projection based on a window id */
projection_t* find_source_window(Window window);
projection_t* find_target_window(Window window);
projection_t* find_any_window(Window window);

/* Update the brightness setting, but don't actually redraw anything.
   Returns true if the brightness have changed.
*/
int update_brightness(projection_t *proj);


/* Draw entire window */
void project_all(projection_t *proj);

/* Draw the damage recorded in region */
void project_region(projection_t *proj);

/* Draw a given source rectangle */
void project_rectangle(projection_t *proj, XRectangle *rect);

/* Target window has changed size */
void project_target_resized(projection_t *proj, int width, int height);

#endif /* __PLCM_H_INCLUDED__ */
