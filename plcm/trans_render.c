
#include <X11/extensions/Xrender.h>

#include <stdlib.h>
#include <string.h>

#include "plcm.h"

static int render_event_base, render_error_base;

typedef struct trans_render_s
{
  trans_base_t base;

  Picture source_picture;
  Picture target_picture;

  Pixmap mask_pixmap;
  Picture mask_picture;

} trans_render_t;


static void render_trans_destroy(trans_base_t *trans);
static void render_trans_rectangle(trans_base_t *trans, XRectangle *rect);


int check_render()
{
  int major, minor;
  
  if (XRenderQueryExtension(disp, &render_event_base, &render_error_base))
    {
      if (!XRenderQueryVersion(disp, &major, &minor))
	{
	  info("could not get render version");
	  return 0;
	}

      if (!XRenderQueryFormats(disp))
	{
	  info("could not query render formats");
	  return 0;
	}

      {
	XRenderPictFormat *format = XRenderFindStandardFormat(disp, PictStandardA8);

	info("format: %p", format);
      }

      info("found render extension %d.%d", major, minor);
      return 1;
    }
  else
    {
      info("no render extension");
      return 0;
    }
}



static trans_ops_t render_ops = {
  render_trans_destroy,
  render_trans_rectangle,
  NULL, /* trans_target_resized */
};


trans_base_t* create_trans_render(projection_t *proj)
{
  trans_render_t *trans;
  XRenderPictFormat *pict_format;
  XRenderPictureAttributes pict_attrs;
  Window dummy_window;
  int dummy_int;
  int depth;
  
  trans = malloc(sizeof(trans_render_t));
  if (trans == NULL)
    {
      info("out of memory allocating trans_render_t");
      return NULL;
    }

  memset(trans, 0, sizeof(trans_render_t));

  trans->base.ops = &render_ops;
  trans->base.proj = proj;

  pict_format = XRenderFindVisualFormat(disp, proj->visual);
  if (pict_format == NULL)
    {
      info("could not find XRenderPictFormat for visual");
      goto error;
    }

  /* Catch pixmap/picture creation errors from here onwards */
  XSync(disp, False);
  last_x_error = 0;
  
  memset(&pict_attrs, 0, sizeof(XRenderPictureAttributes));
  pict_attrs.subwindow_mode = IncludeInferiors;
  
  trans->source_picture =
    XRenderCreatePicture(disp, proj->source_window, pict_format,
			 CPSubwindowMode, &pict_attrs);

  memset(&pict_attrs, 0, sizeof(XRenderPictureAttributes));
  pict_attrs.subwindow_mode = IncludeInferiors;
  
  trans->target_picture =
    XRenderCreatePicture(disp, proj->target_window, pict_format,
			 CPSubwindowMode, &pict_attrs);


  /* FIXME: XFree(pict_format) here? */

  /* Use standard format of 8-bit RGB for mask, must exist */

  pict_format = XRenderFindStandardFormat(disp, PictStandardRGB24);
  if (pict_format == NULL)
    {
      info("could not find XRenderPictFormat for standard format RGB24");
      goto error;
    }
  
  /* Use depth of root window for pixmap */
  if (!XGetGeometry(disp, proj->root, &dummy_window, &dummy_int, &dummy_int,
		    &dummy_int, &dummy_int, &dummy_int, &depth))
    {
      info("failed to get depth of root window");
      goto error;
    }

  trans->mask_pixmap = XCreatePixmap(disp, proj->root, 1, 1, depth);

  /* The mask use separate alphas for the different colour components,
     to allow better brightness control.
  */
  memset(&pict_attrs, 0, sizeof(XRenderPictureAttributes));
  pict_attrs.repeat = True;
  pict_attrs.component_alpha = True;
  
  trans->mask_picture =
    XRenderCreatePicture(disp, trans->mask_pixmap, pict_format,
			 CPRepeat | CPComponentAlpha, &pict_attrs);

  /* FIXME: XFree(pict_format) here? */


  /* Check for creation errors */
  XSync(disp, False);
  if (last_x_error)
    {
      info("error while setting up render projection");
      goto error;
    }

  return (trans_base_t*) trans;

 error:
  if (trans->mask_picture)
    XRenderFreePicture(disp, trans->mask_picture);

  if (trans->mask_pixmap)
    XFreePixmap(disp, trans->mask_pixmap);

  if (trans->target_picture)
    XRenderFreePicture(disp, trans->target_picture);

  if (trans->source_picture)
    XRenderFreePicture(disp, trans->source_picture);

  free(trans);

  return NULL;
}


static void render_trans_destroy(trans_base_t *trans_base)
{
  trans_render_t *trans = (trans_render_t*) trans_base;

  if (trans != NULL)
    {
      XRenderFreePicture(disp, trans->mask_picture);
      XFreePixmap(disp, trans->mask_pixmap);
      XRenderFreePicture(disp, trans->target_picture);
      XRenderFreePicture(disp, trans->source_picture);

      free(trans);
    }
}


static void render_trans_rectangle(trans_base_t *trans_base, XRectangle *rect)
{
  trans_render_t *trans = (trans_render_t*) trans_base;
  projection_t *proj = trans->base.proj;

  if (proj->brightness < 0)
    {
      /* Dim the window by using the brightness as an alpha value when
	 copying the source window into the target.

	 FIXME: calculate alphas for the different colour components
	 to take relative brightness into account.  For now, use a
	 single value for all.
      */

      XRenderColor color;
      int alpha;

      /* Translate into 16-bit positive value */
      alpha = 255 + proj->brightness;
      alpha = (alpha << 8) | alpha;

      color.red = color.green = color.blue = alpha;
      color.alpha = 0xffffU;

      XRenderFillRectangle(disp, PictOpSrc, trans->mask_picture,
			   &color, 0, 0, 1, 1);

      XRenderComposite(disp, PictOpSrc, trans->source_picture,
		       trans->mask_picture, trans->target_picture,
		       rect->x, rect->y, 0, 0,
		       rect->x, rect->y,
		       rect->width, rect->height);
    }
  else
    {
      /* Make the window brighter by adding a value to the source
	 colour components.

	 FIXME: calculate increases for the different colour
	 components to take relative brightness into account.  For
	 now, use a single value for all.
      */

      XRenderColor color;
      int inc;

      /* Translate into 16-bit positive value */
      inc = (proj->brightness << 8) | proj->brightness;

      color.red = color.green = color.blue = inc;
      color.alpha = 0xffffU;

      XRenderFillRectangle(disp, PictOpSrc, trans->target_picture,
			   &color, rect->x, rect->y,
			   rect->width, rect->height);

      XRenderComposite(disp, PictOpAdd, trans->source_picture,
		       None, trans->target_picture,
		       rect->x, rect->y, 0, 0,
		       rect->x, rect->y,
		       rect->width, rect->height);
    }
}
