
#include "plcm.h"

static void handle_message(const XClientMessageEvent *ev);
static void handle_expose(const XExposeEvent *ev);
static void handle_configure(const XConfigureEvent *ev);
static void handle_destroy(const XDestroyWindowEvent *ev);
static void handle_map(const XMapEvent *ev);
static void handle_unmap(const XUnmapEvent *ev);
static void handle_property(const XPropertyEvent *ev);
static void handle_visibility(const XVisibilityEvent *ev);
static void handle_damage(const XDamageNotifyEvent *ev);


void event_loop(void)
{
  while (1)
    {
      XEvent ev;
      XNextEvent(disp, &ev);

      switch (ev.type)
	{
	case ClientMessage:
	  handle_message(&ev.xclient);
	  break;

	case Expose:
	  handle_expose(&ev.xexpose);
	  break;

	case ConfigureNotify:
	  handle_configure(&ev.xconfigure);
	  break;

	case DestroyNotify:
	  handle_destroy(&ev.xdestroywindow);
	  break;

	case MapNotify:
	  handle_map(&ev.xmap);
	  break;

	case UnmapNotify:
	  handle_unmap(&ev.xunmap);
	  break;

	case PropertyNotify:
	  handle_property(&ev.xproperty);
	  break;

	case VisibilityNotify:
	  handle_visibility(&ev.xvisibility);
	  break;

	default:
	  if (ev.type == damage_event_base + XDamageNotify)
	    handle_damage((XDamageNotifyEvent*) &ev.xany);
	}
    }
}


static void handle_message(const XClientMessageEvent *ev)
{
  if (ev->window != ctrl_win)
    {
      info("received message for unexpected window 0x%08lx",
	   (unsigned long) ev->window);
      return;
    }

  if (ev->message_type == _PLCM_ENABLE && ev->format == 32)
    {
      Window source, target;
      projection_t* proj;

      source = ev->data.l[0];
      target = ev->data.l[1];

      info("recieved ENABLE message for 0x%08x -> 0x%08x",
	   (int) source, (int) target);

      proj = add_projection(source, target);

      if (proj != NULL)
	{
	  info("projection enabled");
	}
      else
	{
	  info("projection NOT enabled");
	}
    }
  else if (ev->message_type == _PLCM_DISABLE && ev->format == 32)
    {
      Window source, target;
      projection_t* proj;

      source = ev->data.l[0];
      target = ev->data.l[1];

      info("recieved DISABLE message for 0x%08x -> 0x%08x",
	   (int) source, (int) target);

      proj = find_source_window(source);
      if (proj == NULL || proj->target_window != target)
	{
	  info("DISABLE for unknown projection, ignoring");
	}
      else 
	{
	  free_projection(proj);
	}
    }
  else
    {
      info("unknown message: %d (format %d)",
	   (int) ev->message_type, ev->format);
      return;
    }
}


static void handle_expose(const XExposeEvent *ev)
{
  projection_t *proj = find_target_window(ev->window);

  if (proj)
    {
      XRectangle rect;

      /* Translate from target to source coordinated */
      rect.x = ev->x + proj->source_geometry.x;
      rect.y = ev->y + proj->source_geometry.y;
      rect.width = ev->width;
      rect.height = ev->height;
      
      project_rectangle(proj, &rect);
    }
}


static void handle_configure(const XConfigureEvent *ev)
{
  projection_t *proj = find_any_window(ev->window);

  if (proj)
    {
      /* Update the geometry info for the windows.  But don't trigger
	 a redraw, wait for Expose or Damage events for that.
       */
      if (proj->target_window == ev->window)
	{
	  project_target_resized(proj, ev->width, ev->height);
	}
      else
	{
	  /* Ignore the border when it comes to projection */
	  proj->source_geometry.x = ev->x + ev->border_width;
	  proj->source_geometry.y = ev->y + ev->border_width;
	  proj->source_geometry.width = ev->width;
	  proj->source_geometry.height = ev->height;
	}
    }
}


static void handle_destroy(const XDestroyWindowEvent *ev)
{
  projection_t *proj = find_any_window(ev->window);

  if (proj)
    {
      info("0x%08x: destroyed, taking down projection",
	   (int) ev->window);

      /* Reset either window parameter in proj to avoid getting
	 XBadWindow errors during shutdown.
      */
      if (proj->target_window == ev->window)
	proj->target_window = None;
      else
	proj->source_window = None;

      free_projection(proj);
    }
}


static void handle_map(const XMapEvent *ev)
{
  projection_t *proj = find_any_window(ev->window);

  if (proj)
    {
      info("0x%08x: mapped", (int) ev->window);

      if (proj->target_window == ev->window)
	proj->target_is_visible = 1;
      else
	proj->source_is_mapped = 1;
    }
}


static void handle_unmap(const XUnmapEvent *ev)
{
  projection_t *proj = find_any_window(ev->window);

  if (proj)
    {
      info("0x%08x: unmapped", (int) ev->window);

      if (proj->target_window == ev->window)
	proj->target_is_visible = 0;
      else
	proj->source_is_mapped = 0;
    }
}


static void handle_property(const XPropertyEvent *ev)
{
  projection_t *proj = find_target_window(ev->window);

  if (!proj)
    return;

  if (ev->atom == _PLCM_BRIGHTNESS)
    {
      if (update_brightness(proj))
	{
	  /* Need redraw */
	  project_all(proj);
	}
    }
}


static void handle_visibility(const XVisibilityEvent *ev)
{
  projection_t *proj = find_target_window(ev->window);

  if (proj)
    {
      proj->target_is_visible = (ev->state != VisibilityFullyObscured);
      info("0x%08x: is visible: %d",
	   (int) proj->target_window,
	   proj->target_is_visible);
    }
}


static void handle_damage(const XDamageNotifyEvent *ev)
{
  projection_t *proj = find_source_window(ev->drawable);

  if (proj)
    {
      /* Get the accumulated damage */
      XDamageSubtract(disp, proj->damage, None, proj->damage_region);

      project_region(proj);
    }
}
