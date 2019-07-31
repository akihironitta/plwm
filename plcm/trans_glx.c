
#include <stdlib.h>
#include <string.h>

#include <GL/gl.h>
#include <GL/glx.h>
#include <GL/glxext.h>

#include "plcm.h"


typedef struct trans_glx_s
{
  trans_base_t base;

  /* Common fields */
  XVisualInfo visual_info;
  
  /* Fields created differently in 1.2 and 1.3 */
  GLXContext context;

  /* Following fields are only used by GLX_13 */  
  GLXFBConfig fb_config;
  GLXWindow glx_source_window;
  GLXWindow glx_target_window;

} trans_glx_t;


static int glx_event_base, glx_error_base;


static trans_glx_t* create_trans_glx_common(projection_t *proj, trans_ops_t *ops);
static void glx_common_trans_destroy(trans_glx_t *trans);


glx_version_t check_glx()
{
  /* Sorry, I can't this to work and can't be bothered at the moment.
     Seems to be a problem with rendering over the reparented window
     into the proxy window.  In an GC IncludeInferiors can be set to
     work around that, but I can't find any corresponding flag for GLX
     contexts.

     The render extension should be all anyone needs to set the
     brightness of windows, but zooming would rquire GLX.
  */
  
  /*
  int major, minor;
  
  if (glXQueryExtension(disp, &glx_event_base, &glx_error_base))
    {
      if (!glXQueryVersion(disp, &major, &minor))
	die("could not get glx version");

      info("found glx extension %d.%d", major, minor);

      if (major == 1 && minor == 2)
	return GLX_12;
      else if (major == 1 && minor == 3)
	return GLX_13;
      else
	info("unsupported glx version");
    }
  else
    info("no glx extension");
  */

  return NO_GLX;
}


/* GLX 1.2 implementation */

static void glx12_trans_destroy(trans_base_t *trans);
static void glx12_trans_rectangle(trans_base_t *trans, XRectangle *rect);

static trans_ops_t glx12_ops = {
  glx12_trans_destroy,
  glx12_trans_rectangle,
  NULL, /* trans_target_resized */
};


trans_base_t* create_trans_glx12(projection_t *proj)
{
  trans_glx_t *trans;

  trans = create_trans_glx_common(proj, &glx12_ops);
  if (trans == NULL)
    return NULL;

  trans->context = glXCreateContext(disp, &trans->visual_info, NULL, True);
  if (trans->context == NULL)
    {
      info("failed to create glx 1.2 context");
      glx_common_trans_destroy(trans);
      return NULL;
    }
  
  return (trans_base_t*) trans;
}


static void glx12_trans_destroy(trans_base_t *trans_base)
{
  glx_common_trans_destroy((trans_glx_t*) trans_base);
}


static void glx12_trans_rectangle(trans_base_t *trans_base, XRectangle *rect)
{
  trans_glx_t *trans = (trans_glx_t*) trans_base;
  projection_t *proj = trans->base.proj;
  
  int x, y;
  int max_rows, remaining_rows;
  GLfloat scale;
  GLfloat bias;

  /* Translate from X coordinates (left,top) to glX coordinates (left, bottom) */
  x = rect->x;
  y = proj->source_geometry.height - rect->y - rect->height;

  /* Render brightness.  This doesn't take the relative
     intensities of R, G, and B into account, and thus will slightly
     change the perceived color when changing the brightness.
  */
  if (proj->brightness < 0)
    {
      /* Transpose -255,0 to [0.0, 1.0] */
      scale = (255 + proj->brightness) / 255.0;
      bias = 0;
    }
  else
    {
      /* Transpose 0,255 to [0.0, 1.0] */
      bias = proj->brightness / 255.0;
      scale = 1.0;
    }
	  
  /* With GLX 1.2 we must bounce the pixels in our memory.  Lose
     lose.  Don't transfer more than 512k at a time, though.
  */
  max_rows = 0x80000 / (rect->width * 3 + 4);
  if (max_rows < 1)
    max_rows = 1;

  void *mem = malloc((rect->width * 3 + 4) * max_rows);

  if (mem == NULL)
    {
      info("out of memory");
      return;
    }
	  
  for (remaining_rows = rect->height;
       remaining_rows > 0;
       remaining_rows -= max_rows)
    {
      if (remaining_rows < max_rows)
	max_rows = remaining_rows;
      
      info("copying %d rows to (%d,%d)", max_rows, x, y);
      
      glXMakeCurrent(disp, proj->source_window, trans->context);
      glReadBuffer(GL_FRONT);

      glPixelTransferf(GL_RED_SCALE, 1.0);
      glPixelTransferf(GL_RED_BIAS, 0.0);
      glPixelTransferf(GL_GREEN_SCALE, 1.0);
      glPixelTransferf(GL_GREEN_BIAS, 0.0);
      glPixelTransferf(GL_BLUE_SCALE, 1.0);
      glPixelTransferf(GL_BLUE_BIAS, 0.0);

      glReadPixels(x, y, rect->width, max_rows, GL_RGB, GL_UNSIGNED_BYTE, mem);

      glXMakeCurrent(disp, proj->target_window, trans->context);
      glViewport(0, 0, proj->target_width, proj->target_height);

      glMatrixMode(GL_PROJECTION);
      glLoadIdentity();
      glOrtho(0.0, (GLfloat) proj->target_width,
	      0.0, (GLfloat) proj->target_height,
	      -1.0, 1.0);
      glMatrixMode(GL_MODELVIEW);
      glLoadIdentity();

      glRasterPos2i(x, y);
      glDrawBuffer(GL_FRONT);

      glPixelTransferf(GL_RED_SCALE, scale);
      glPixelTransferf(GL_RED_BIAS, bias);
      glPixelTransferf(GL_GREEN_SCALE, scale);
      glPixelTransferf(GL_GREEN_BIAS, bias);
      glPixelTransferf(GL_BLUE_SCALE, scale);
      glPixelTransferf(GL_BLUE_BIAS, bias);

      glDrawPixels(rect->width, max_rows, GL_RGB, GL_UNSIGNED_BYTE, mem);

      y += max_rows;
    }

  glFlush();
  glXMakeCurrent(disp, None, NULL);
  free(mem);

  glXWaitGL();
}



/* GLX 1.3 implementation */

static void glx13_trans_destroy(trans_base_t *trans_base);
static void glx13_trans_rectangle(trans_base_t *trans_base, XRectangle *rect);

static trans_ops_t glx13_ops = {
  glx13_trans_destroy,
  glx13_trans_rectangle,
  NULL, /* trans_target_resized */
};


trans_base_t* create_trans_glx13(projection_t *proj)
{
  trans_glx_t *trans;

  GLXFBConfig *fb_confs;
  int num_fb_confs;
  int fb_attrs[] = {
    GLX_X_VISUAL_TYPE, GLX_DONT_CARE, /* over-written below */
    None
  };

  trans = create_trans_glx_common(proj, &glx13_ops);
  if (trans == NULL)
    return NULL;

  switch (trans->visual_info.class)
    {
    case TrueColor:
      fb_attrs[1] = GLX_TRUE_COLOR;
      break;
	  
    case DirectColor:
      fb_attrs[1] = GLX_DIRECT_COLOR;
      break;

    default:
      info("unsupported visual class");
      goto error;
    }

  // FIXME: find screen number
  fb_confs = glXChooseFBConfig(disp, 0, fb_attrs, &num_fb_confs);
  if (fb_confs == NULL)
    {
      info("couldn't find any glXFBConfig");
      goto error;
    }

  trans->fb_config = fb_confs[0];
  XFree(fb_confs);
      
  trans->context = glXCreateNewContext(disp, trans->fb_config,
				       GLX_RGBA_TYPE, NULL, False);

  if (trans->context == NULL)
    {
      info("failed to create glX 1.3 context");
      goto error;
    }

  trans->glx_source_window = glXCreateWindow(disp, trans->fb_config,
					     proj->source_window, NULL);

  trans->glx_target_window = glXCreateWindow(disp, trans->fb_config,
					     proj->target_window, NULL);

  return (trans_base_t*) trans;

 error:
  glx13_trans_destroy((trans_base_t*) trans);
  return NULL;
}


static void glx13_trans_destroy(trans_base_t *trans_base)
{
  trans_glx_t *trans = (trans_glx_t*) trans_base;

  if (trans != NULL)
    {
      if (trans->glx_source_window)
	glXDestroyWindow(disp, trans->glx_source_window);

      if (trans->glx_target_window)
	glXDestroyWindow(disp, trans->glx_target_window);

      glx_common_trans_destroy(trans);
    }
}


static void glx13_trans_rectangle(trans_base_t *trans_base, XRectangle *rect)
{
  trans_glx_t *trans = (trans_glx_t*) trans_base;
  projection_t *proj = trans->base.proj;

  int x, y;
  GLfloat scale;
  GLfloat bias;

  /* Translate from X coordinates (left,top) to glX coordinates (left, bottom) */
  x = rect->x;
  y = proj->source_geometry.height - rect->y - rect->height;

  /* Render brightness.  This doesn't take the relative
     intensities of R, G, and B into account, and thus will slightly
     change the perceived color when changing the brightness.
  */
  if (proj->brightness < 0)
    {
      /* Transpose -255,0 to [0.0, 1.0] */
      scale = (255 + proj->brightness) / 255.0;
      bias = 0;
    }
  else
    {
      /* Transpose 0,255 to [0.0, 1.0] */
      bias = proj->brightness / 255.0;
      scale = 1.0;
    }
	  
  /* With glX 1.3 we can render directly from the source to the
     target window.
  */
  if (!glXMakeContextCurrent(disp,
			     trans->glx_target_window,
			     trans->glx_source_window,
			     trans->context))
    {
      info("failed to set glX drawables");
      return;
    }

  glPixelTransferf(GL_RED_SCALE, scale);
  glPixelTransferf(GL_RED_BIAS, bias);
  glPixelTransferf(GL_GREEN_SCALE, scale);
  glPixelTransferf(GL_GREEN_BIAS, bias);
  glPixelTransferf(GL_BLUE_SCALE, scale);
  glPixelTransferf(GL_BLUE_BIAS, bias);
  glPixelTransferf(GL_ALPHA_SCALE, 1.0);
  glPixelTransferf(GL_ALPHA_BIAS, 0.0);

  glRasterPos2i(x, y);
  glCopyPixels(x, y, rect->width, rect->height, GL_COLOR);

  glXMakeContextCurrent(disp, None, None, NULL);
  glFlush();

  // glXWaitGL();
}


/* Common code for both 1.2 and 1.3 */

static trans_glx_t* create_trans_glx_common(projection_t *proj, trans_ops_t *ops)
{
  trans_glx_t *trans;
  XVisualInfo visual_template;
  XVisualInfo *visual_info = NULL;
  int num_visuals;

  trans = malloc(sizeof(trans_glx_t));
  if (trans == NULL)
    {
      info("out of memory allocating trans_glx_t");
      return NULL;
    }

  memset(trans, 0, sizeof(trans_glx_t));

  trans->base.ops = ops;
  trans->base.proj = proj;


  /* Find out the full XVisualInfo for visual ID so we can create a
     glX context for it.  All visual IDs are unique, so we should only
     get one.
  */
  visual_template.visualid = XVisualIDFromVisual(proj->visual);
  visual_info = XGetVisualInfo(disp, VisualIDMask, &visual_template, &num_visuals);

  if (visual_info == NULL)
    {
      info("couldn't get visual info");
      glx_common_trans_destroy(trans);
      return NULL;
    }

  trans->visual_info = visual_info[0];
  XFree(visual_info);

  return trans;

}


static void glx_common_trans_destroy(trans_glx_t *trans)
{
  if (trans != NULL)
    {
      if (trans->context != NULL)
	glXDestroyContext(disp, trans->context);

      free(trans);
    }
}
