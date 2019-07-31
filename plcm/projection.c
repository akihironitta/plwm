
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

#include "plcm.h"

static int init_projection(projection_t *proj);
static void destroy_projection(projection_t *proj);

static projection_t* projections = NULL;

projection_t* add_projection(Window source, Window target)
{
  projection_t* proj;

  /* These two windows must not be involved in any existing
     projection
  */
  for (proj = projections; proj != NULL; proj = proj->next)
    {
      if (proj->source_window == source
	  || proj->source_window == target
	  || proj->target_window == source
	  || proj->target_window == target)
	{
	  info("requested projection 0x%08x -> 0x%08x matches existing projection 0x%08x -> 0x%08x",
	       (int) source, (int) target,
	       (int) proj->source_window,
	       (int) proj->target_window);
	  return NULL;
	}
    }
  
  proj = malloc(sizeof(projection_t));
  if (proj == NULL)
    {
      info("out of memory");
      return NULL;
    }

  memset(proj, 0, sizeof(projection_t));

  proj->source_window = source;
  proj->target_window = target;

  if (!init_projection(proj))
    {
      info("failed to init projection");

      free(proj);
      return NULL;
    }

  proj->next = projections;
  projections = proj;

  return proj;
};


void free_projection(projection_t *proj)
{
  projection_t **prev;

  for (prev = &projections; *prev != NULL; prev = &((*prev)->next))
    {
      if (*prev == proj)
	{
	  *prev = proj->next;

	  destroy_projection(proj);
	  free(proj);
	  return;
	}
    }

  die("internal error: freeing projection not in list");
}


projection_t* find_source_window(Window window)
{
  projection_t* proj;

  for (proj = projections; proj != NULL; proj = proj->next)
    {
      if (proj->source_window == window)
	return proj;
    }

  return NULL;
}


projection_t* find_target_window(Window window)
{
  projection_t* proj;

  for (proj = projections; proj != NULL; proj = proj->next)
    {
      if (proj->target_window == window)
	return proj;
    }

  return NULL;
}


projection_t* find_any_window(Window window)
{
  projection_t* proj;

  for (proj = projections; proj != NULL; proj = proj->next)
    {
      if (proj->target_window == window
	  || proj->source_window == window)
	return proj;
    }

  return NULL;
}


static int init_projection(projection_t *proj)
{
  XGCValues gc_values;
  XWindowAttributes target_attr, source_attr;
  XSetWindowAttributes set_attr;

  /* Get some info about the windows and check that we can handle this
     projection
  */

  if (!XGetWindowAttributes(disp, proj->target_window, &target_attr))
    {
      info("failed to get attributes for target 0x%08x",
	   (int) proj->target_window);
      return 0;
    }

  if (!XGetWindowAttributes(disp, proj->source_window, &source_attr))
    {
      info("failed to get attributes for source 0x%08x",
	   (int) proj->source_window);
      return 0;
    }


  /* Windows must belong to the same screen... */
  if (target_attr.root != source_attr.root)
    {
      info("can't project from one screen to another");
      return 0;
    }
  
  /* ...and have same depth... */
  if (target_attr.depth != source_attr.depth)
    {
      info("can't project between different depths");
      return 0;
    }

  /* ...and the same visual. */
  if (XVisualIDFromVisual(target_attr.visual)
      != XVisualIDFromVisual(source_attr.visual))
    {
      info("can't project between different visuals");
      return 0;
    }


  /* Projection looks ok */

  proj->screen = target_attr.screen;
  proj->root = target_attr.root;
  proj->visual = target_attr.visual;

  /* Translate map state to target visibility */
  proj->target_is_visible = (target_attr.map_state == IsViewable);
  
  proj->target_width = target_attr.width;
  proj->target_height = target_attr.height;
  
  proj->source_is_mapped = (source_attr.map_state != IsUnmapped);

  /* Ignore the border when it comes to projection */
  proj->source_geometry.x = source_attr.x + source_attr.border_width;
  proj->source_geometry.y = source_attr.y + source_attr.border_width;
  proj->source_geometry.width = source_attr.width;
  proj->source_geometry.height = source_attr.height;
  

  /* Set up required event masks */

  /* For target window, we must know about its state (mapped,
     destroyed, size), exposure, visibility (to know if there's any
     point in rendering damage) and the rendering properties set by
     plwm.
  */

  set_attr.event_mask = (StructureNotifyMask
			 | ExposureMask
			 | VisibilityChangeMask
			 | PropertyChangeMask);

  XChangeWindowAttributes(disp, proj->target_window, CWEventMask, &set_attr);
  

  /* For source window, we only need to know about its state (mapped,
     destroyed, size).
  */

  set_attr.event_mask = StructureNotifyMask;
  XChangeWindowAttributes(disp, proj->source_window, CWEventMask, &set_attr);


  /* Create a normal X context for copying pixels when no
     transformation is required.
  */
  gc_values.subwindow_mode = IncludeInferiors;
  proj->gc = XCreateGC(disp, proj->root, GCSubwindowMode, &gc_values);


  /* Fetch any initial render settings */
  update_brightness(proj);


  /* Ask for damage notification.  We use the model where we're told
     whenever some damage occur, and then render all that damage in a
     batch.  Might not be optimal, but easy(ish).
  */

  proj->damage = XDamageCreate(disp, proj->source_window, XDamageReportNonEmpty);
  proj->damage_region = XFixesCreateRegion(disp, NULL, 0);


  /* Create trans object */
  proj->trans = create_trans(proj);
  if (proj->trans == NULL)
    {
      info("failed to create trans object");
      return 0;
    }

  /* And finally render the initial contents  */
  project_all(proj);

  return 1;
}


static void destroy_projection(projection_t *proj)
{
  XSetWindowAttributes attr;

  if (proj->trans)
    {
      proj->trans->ops->destroy(proj->trans);
      proj->trans = NULL;
    }

  XFixesDestroyRegion(disp, proj->damage_region);
  XDamageDestroy(disp, proj->damage);

  /* We're no longer interested in any events on these windows
   */
  attr.event_mask = NoEventMask;

  if (proj->target_window != None)
    XChangeWindowAttributes(disp, proj->target_window, CWEventMask, &attr);

  if (proj->source_window != None)
    XChangeWindowAttributes(disp, proj->source_window, CWEventMask, &attr);

  if (proj->gc != None)
    XFreeGC(disp, proj->gc);
}


int update_brightness(projection_t *proj)
{
  Atom type;
  int format;
  unsigned long items;
  unsigned long more_bytes;
  unsigned char *mem;
  long *data;

  int old_brightness = proj->brightness;
  
  if (XGetWindowProperty(disp, proj->target_window, _PLCM_BRIGHTNESS,
			  0, 1, False, XA_INTEGER, &type, &format,
			  &items, &more_bytes, &mem) == Success
      && type == XA_INTEGER
      && format == 32
      && items == 1)
    {
      data = (long*) mem;
      proj->brightness = data[0];

      XFree(mem);

      if (proj->brightness > 255)
	proj->brightness = 255;
      else if (proj->brightness < -255)
	proj->brightness = -255;
      
      info("0x%08x: brightness = %d",
	   (int) proj->target_window,
	   proj->brightness);
    }
  else
    {
      proj->brightness = 0;

      info("0x%08x: brightness = 0 (no _PLCM_BRIGHTNESS)",
	   (int) proj->target_window);
    }

  return old_brightness != proj->brightness;
}


void project_region(projection_t *proj)
{
  XRectangle *rects;
  int num_rects;
  int i;
  
  rects = XFixesFetchRegion(disp, proj->damage_region, &num_rects);

  for (i = 0; i < num_rects; ++i)
    {
      project_rectangle(proj, rects + i);
    }

  XFree(rects);
}


void project_all(projection_t *proj)
{
  XRectangle rect;

  rect.x = 0;
  rect.y = 0;
  rect.width = proj->source_geometry.width;
  rect.height = proj->source_geometry.height;

  project_rectangle(proj, &rect);
}


void project_rectangle(projection_t *proj, XRectangle *rect)
{
  /*
  info("0x%08x: drawing %d,%d %dx%d",
       (int) proj->source_window,
       rect->x, rect->y, rect->width, rect->height);
  */
  
  if (proj->brightness == 0)
    {
      /* If no effects are active, copy pixels directly */

      XCopyArea(disp,
		proj->source_window,
		proj->target_window,
		proj->gc,
		rect->x, rect->y, rect->width, rect->height,
		rect->x - proj->source_geometry.x,
		rect->y - proj->source_geometry.y);
    }
  else
    {
      /* Let the trans object handle the effects */
      proj->trans->ops->trans_rectangle(proj->trans, rect);
    }
}


void project_target_resized(projection_t *proj, int width, int height)
{
  proj->target_width = width;
  proj->target_height = height;

  if (proj->trans->ops->target_resized)
    proj->trans->ops->target_resized(proj->trans);
}

