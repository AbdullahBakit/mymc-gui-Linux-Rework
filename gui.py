#
# gui.py
#
# By Ross Ridge
# Rework by Abdullah Bakit
# Public Domain
#
# Ported for Python 3 / Linux
#

"""Graphical user-interface for mymc."""

_SCCS_ID = "@(#) mymc gui.py 1.8 22/02/05 19:20:59\n"

import os
import sys
import struct
import io
import time
import traceback
from functools import partial

import wx

import ps2mc
import ps2save
import guires

# Global Exception Handler to prevent silent crashes
def handle_exception(exc_type, exc_value, exc_traceback):
    err_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print("FATAL ERROR:\n", err_msg)
    wx.MessageBox(f"A fatal error occurred:\n\n{err_msg}", "Application Error", wx.OK | wx.ICON_ERROR)

sys.excepthook = handle_exception

# Native OpenGL Implementation
try:
    from wx import glcanvas
    import OpenGL.GL as gl
    import OpenGL.GLU as glu
    has_opengl = True
except ImportError:
    has_opengl = False
    print("Warning: PyOpenGL not found. 3D Icons disabled.")

lighting_none = {"lighting": False, "vertex_diffuse": False, "alt_lighting": False, "ambient": [0, 0, 0, 0]}
lighting_icon = {"lighting": True, "vertex_diffuse": True, "alt_lighting": False, "ambient": [0.2, 0.2, 0.2, 1.0]}
lighting_alternate = {"lighting": True, "vertex_diffuse": True, "alt_lighting": True, "ambient": [0.5, 0.5, 0.5, 1]}
lighting_alternate2 = {"lighting": True, "vertex_diffuse": False, "alt_lighting": True, "ambient": [0.3, 0.3, 0.3, 1]}

camera_default = [0, 4, -8]
camera_high = [0, 7, -6]
camera_near = [0, 3, -6]
camera_flat = [0, 2, -7.5]

def get_dialog_units(win):
    return win.ConvertDialogToPixels((1, 1))[0]

def single_title(title):
    try:
        t0 = title[0].decode('utf-8', 'ignore') if isinstance(title[0], bytes) else str(title[0])
        t1 = title[1].decode('utf-8', 'ignore') if isinstance(title[1], bytes) else str(title[1])
        full_title = t0 + " " + t1
        return u" ".join(full_title.split())
    except Exception:
        return "Unknown Title"

def _get_icon_resource_as_images(name):
    ico = guires.resources[name]
    images = []
    f = io.BytesIO(ico)
    count = struct.unpack("<HHH", ico[0:6])[2]
    for i in range(count):
        f.seek(0)
        images.append(wx.Image(f, wx.BITMAP_TYPE_ICO, i))
    return images
    
def get_icon_resource(name):
    bundle = wx.IconBundle()
    for img in _get_icon_resource_as_images(name):
        bmp = wx.Bitmap(img)
        icon = wx.Icon(bmp)
        bundle.AddIcon(icon)
    return bundle

def get_icon_resource_bmp(name, size):
    best = None
    best_size = (0, 0)
    for img in _get_icon_resource_as_images(name):
        sz = (img.GetWidth(), img.GetHeight())
        if sz == size:
            return wx.Bitmap(img)
        if sz[0] >= size[0] and sz[1] >= size[1]:
            if ((best_size[0] < size[0] or best_size[1] < size[1])
                or sz[0] * sz[1] < best_size[0] * best_size[1]):
                best = img
                best_size = sz
        elif sz[0] * sz[1] > best_size[0] * best_size[1]:
            best = img
            best_size = sz
    img = best.Rescale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
    return wx.Bitmap(img)


class dirlist_control(wx.ListCtrl):
    def __init__(self, parent, evt_focus, evt_select, config):
        self.config = config
        self.selected = set()
        self.evt_select = evt_select
        wx.ListCtrl.__init__(self, parent, wx.ID_ANY, style = wx.LC_REPORT)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.evt_col_click)
        self.Bind(wx.EVT_LIST_ITEM_FOCUSED, evt_focus)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.evt_item_selected)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.evt_item_deselected)

    def _update_dirtable(self, mc, dir):
        self.dirtable = []
        enc = "unicode"
        if self.config.get_ascii():
            enc = "ascii"
        for ent in dir:
            if not ps2mc.mode_is_dir(ent[0]):
                continue
                
            dir_str = ent[8].decode('utf-8', 'ignore') if isinstance(ent[8], bytes) else str(ent[8])
            dirname = "/" + dir_str
            s = mc.get_icon_sys(dirname)
            if s is None:
                continue
            a = ps2save.unpack_icon_sys(s)
            size = mc.dir_size(dirname)
            title = ps2save.icon_sys_title(a, encoding = enc)
            self.dirtable.append((ent, s, size, title))
        
    def update_dirtable(self, mc):
        self.dirtable = []
        if mc is None:
            return
        dir = mc.dir_open("/")
        try:
            self._update_dirtable(mc, dir)
        finally:
            dir.close()

    def get_dir_name(self, i): 
        n = self.dirtable[i][0][8]
        return n.decode('utf-8', 'ignore') if isinstance(n, bytes) else str(n)
        
    def get_dir_title(self, i): return str(self.dirtable[i][3])
    def get_dir_size(self, i): return int(self.dirtable[i][2])
    def get_dir_modified(self, i):
        m = list(self.dirtable[i][0][6])
        m.reverse()
        return m

    def sort_items(self, key):
        def cmp_items(i1, i2):
            try:
                a1 = key(i1)
                a2 = key(i2)
                if a1 < a2: return -1
                if a1 > a2: return 1
                return 0
            except Exception:
                return 0
        self.SortItems(cmp_items)
        
    def evt_col_click(self, event):
        col = event.GetColumn()
        if col == 0: key = self.get_dir_name
        elif col == 1: key = self.get_dir_size
        elif col == 2: key = self.get_dir_modified
        elif col == 3: key = self.get_dir_title
        self.sort_items(key)

    def evt_item_selected(self, event):
        self.selected.add(event.GetData())
        self.evt_select(event)
        
    def evt_item_deselected(self, event):
        self.selected.discard(event.GetData())
        self.evt_select(event)
        
    def update(self, mc):
        self.ClearAll()
        self.selected = set()
        self.InsertColumn(0, "Directory")
        self.InsertColumn(1, "Size")
        self.InsertColumn(2, "Modified")
        self.InsertColumn(3, "Description")
        li = self.GetColumn(1)
        li.SetAlign(wx.LIST_FORMAT_RIGHT)
        li.SetText("Size")
        self.SetColumn(1, li)
        
        self.update_dirtable(mc)
        empty = (len(self.dirtable) == 0)
        self.Enable(not empty)
        if empty: return
        
        for (i, a) in enumerate(self.dirtable):
            (ent, icon_sys, size, title) = a
            
            dir_str = ent[8].decode('utf-8', 'ignore') if isinstance(ent[8], bytes) else str(ent[8])
            li = self.InsertItem(i, dir_str)
            
            self.SetItem(li, 1, "%dK" % (size // 1024))
            m = ent[6]
            self.SetItem(li, 2, ("%04d-%02d-%02d %02d:%02d" % (m[5], m[4], m[3], m[2], m[1])))
            self.SetItem(li, 3, single_title(title))
            self.SetItemData(li, i)

        du = get_dialog_units(self)
        for i in range(4):
            self.SetColumnWidth(i, wx.LIST_AUTOSIZE)
            self.SetColumnWidth(i, self.GetColumnWidth(i) + du)
        self.sort_items(self.get_dir_name)


class icon_window(glcanvas.GLCanvas if has_opengl else wx.Window):
    """Displays a save file's 3D icon using native OpenGL."""
    
    ID_CMD_ANIMATE        = 201
    ID_CMD_LIGHT_NONE     = 202
    ID_CMD_LIGHT_ICON     = 203
    ID_CMD_LIGHT_ALT1     = 204
    ID_CMD_LIGHT_ALT2     = 205
    ID_CMD_CAMERA_FLAT    = 206
    ID_CMD_CAMERA_DEFAULT = 207
    ID_CMD_CAMERA_NEAR    = 209
    ID_CMD_CAMERA_HIGH    = 210

    def append_menu_options(self, win, menu):
        menu.AppendCheckItem(icon_window.ID_CMD_ANIMATE, "Animate Icons")
        menu.AppendSeparator()
        menu.AppendRadioItem(icon_window.ID_CMD_LIGHT_NONE, "Lighting Off")
        menu.AppendRadioItem(icon_window.ID_CMD_LIGHT_ICON, "Icon Lighting")
        menu.AppendRadioItem(icon_window.ID_CMD_LIGHT_ALT1, "Alternate Lighting")
        menu.AppendRadioItem(icon_window.ID_CMD_LIGHT_ALT2, "Alternate Lighting 2")
        menu.AppendSeparator()
        menu.AppendRadioItem(icon_window.ID_CMD_CAMERA_FLAT, "Camera Flat")
        menu.AppendRadioItem(icon_window.ID_CMD_CAMERA_DEFAULT, "Camera Default")
        menu.AppendRadioItem(icon_window.ID_CMD_CAMERA_NEAR, "Camera Near")
        menu.AppendRadioItem(icon_window.ID_CMD_CAMERA_HIGH, "Camera High")

        bind_menu = partial(win.Bind, wx.EVT_MENU)
        bind_menu(self.evt_menu_animate, None, icon_window.ID_CMD_ANIMATE)
        bind_menu_light = partial(bind_menu, self.evt_menu_light, None)
        bind_menu_light(icon_window.ID_CMD_LIGHT_NONE)
        bind_menu_light(icon_window.ID_CMD_LIGHT_ICON)
        bind_menu_light(icon_window.ID_CMD_LIGHT_ALT1)
        bind_menu_light(icon_window.ID_CMD_LIGHT_ALT2)

        bind_menu_camera = partial(bind_menu, self.evt_menu_camera, None)
        bind_menu_camera(icon_window.ID_CMD_CAMERA_FLAT)
        bind_menu_camera(icon_window.ID_CMD_CAMERA_DEFAULT)
        bind_menu_camera(icon_window.ID_CMD_CAMERA_NEAR)
        bind_menu_camera(icon_window.ID_CMD_CAMERA_HIGH)

    def __init__(self, parent):
        self.failed = not has_opengl
        if self.failed:
            wx.Window.__init__(self, parent)
            return

        glcanvas.GLCanvas.__init__(self, parent, -1, attribList=[glcanvas.WX_GL_RGBA, glcanvas.WX_GL_DOUBLEBUFFER])
        self.context = None # Created lazily to prevent Linux GTK crashes
        self.init = False

        self.rotation = 0.0
        self.animate = True
        self.camera_pos = camera_default
        self.light_settings = lighting_alternate2
        self.has_icon = False

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_CONTEXT_MENU, self.evt_context_menu)
        
        self.menu = wx.Menu()
        self.append_menu_options(self, self.menu)
        self.timer.Start(16)

    def InitGL(self):
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        self.apply_lighting()

    def apply_lighting(self):
        if not self.light_settings["lighting"]:
            gl.glDisable(gl.GL_LIGHTING)
            return
            
        gl.glEnable(gl.GL_LIGHTING)
        gl.glEnable(gl.GL_LIGHT0)
        gl.glEnable(gl.GL_COLOR_MATERIAL)
        gl.glColorMaterial(gl.GL_FRONT_AND_BACK, gl.GL_AMBIENT_AND_DIFFUSE)
        
        ambient = self.light_settings["ambient"]
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_AMBIENT, ambient)
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
        gl.glLightfv(gl.GL_LIGHT0, gl.GL_POSITION, [1.0, 1.0, 1.0, 0.0])

    def OnSize(self, event):
        wx.CallAfter(self.DoSetViewport)
        event.Skip()

    def DoSetViewport(self):
        if not self.failed and self.context is not None:
            size = self.GetClientSize()
            self.SetCurrent(self.context)
            gl.glViewport(0, 0, size.width, size.height)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        if self.failed: return
        
        try:
            if self.context is None:
                self.context = glcanvas.GLContext(self)
                
            self.SetCurrent(self.context)
            
            if not self.init:
                self.InitGL()
                self.init = True

            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

            if self.has_icon:
                size = self.GetClientSize()
                gl.glMatrixMode(gl.GL_PROJECTION)
                gl.glLoadIdentity()
                if size.height > 0:
                    glu.gluPerspective(45.0, float(size.width) / float(size.height), 0.1, 100.0)

                gl.glMatrixMode(gl.GL_MODELVIEW)
                gl.glLoadIdentity()
                
                glu.gluLookAt(self.camera_pos[0], self.camera_pos[1], self.camera_pos[2], 0, 0, 0, 0, 1, 0)
                gl.glRotatef(self.rotation, 0.0, 1.0, 0.0)

                # Render a spinning placeholder cube
                gl.glBegin(gl.GL_QUADS)
                gl.glColor3f(0.2, 0.6, 1.0)
                vertices = [
                    [1,-1,-1], [1,1,-1], [-1,1,-1], [-1,-1,-1],
                    [1,-1,1], [1,1,1], [-1,1,1], [-1,-1,1],
                    [1,-1,-1], [1,1,-1], [1,1,1], [1,-1,1],
                    [-1,-1,-1], [-1,1,-1], [-1,1,1], [-1,-1,1],
                    [1,1,-1], [-1,1,-1], [-1,1,1], [1,1,1],
                    [1,-1,-1], [-1,-1,-1], [-1,-1,1], [1,-1,1]
                ]
                for v in vertices:
                    gl.glVertex3fv(v)
                gl.glEnd()

            self.SwapBuffers()
            
        except Exception as e:
            print("OpenGL rendering failed safely:", e)
            self.failed = True
            self.timer.Stop()

    def OnTimer(self, event):
        if self.animate and self.has_icon and not self.failed:
            self.rotation += 2.0
            self.Refresh(False)

    def update_menu(self, menu):
        menu.Check(icon_window.ID_CMD_ANIMATE, self.animate)
        menu.Check(self.lighting_id, True)
        menu.Check(self.camera_id, True)
        
    def load_icon(self, icon_sys, icon):
        if self.failed: return
        self.has_icon = (icon_sys is not None)
        self.Refresh(False)

    def set_lighting(self, id):
        if self.failed: return
        self.lighting_id = id
        if id == self.ID_CMD_LIGHT_NONE: self.light_settings = lighting_none
        elif id == self.ID_CMD_LIGHT_ICON: self.light_settings = lighting_icon
        elif id == self.ID_CMD_LIGHT_ALT1: self.light_settings = lighting_alternate
        elif id == self.ID_CMD_LIGHT_ALT2: self.light_settings = lighting_alternate2
        if self.init and self.context is not None:
            self.SetCurrent(self.context)
            self.apply_lighting()
            self.Refresh(False)
        
    def set_animate(self, animate):
        self.animate = animate
        
    def set_camera(self, id):
        if self.failed: return
        self.camera_id = id
        if id == self.ID_CMD_CAMERA_FLAT: self.camera_pos = camera_flat
        elif id == self.ID_CMD_CAMERA_DEFAULT: self.camera_pos = camera_default
        elif id == self.ID_CMD_CAMERA_NEAR: self.camera_pos = camera_near
        elif id == self.ID_CMD_CAMERA_HIGH: self.camera_pos = camera_high
        self.Refresh(False)
        
    def evt_context_menu(self, event):
        self.update_menu(self.menu)
        self.PopupMenu(self.menu)

    def evt_menu_animate(self, event): self.set_animate(not self.animate)
    def evt_menu_light(self, event): self.set_lighting(event.GetId())
    def evt_menu_camera(self, event): self.set_camera(event.GetId())

class gui_config(wx.Config):
    memcard_dir = "Memory Card Directory"
    savefile_dir = "Save File Directory"
    ascii = "ASCII Descriptions"
    
    def __init__(self):
        wx.Config.__init__(self, "mymc", "Ross Ridge", style = wx.CONFIG_USE_LOCAL_FILE)

    def get_memcard_dir(self, default = None): return self.Read(gui_config.memcard_dir, default)
    def set_memcard_dir(self, value): return self.Write(gui_config.memcard_dir, value)
    def get_savefile_dir(self, default = None): return self.Read(gui_config.savefile_dir, default)
    def set_savefile_dir(self, value): return self.Write(gui_config.savefile_dir, value)
    def get_ascii(self, default = False): return bool(self.ReadInt(gui_config.ascii, int(bool(default))))
    def set_ascii(self, value): return self.WriteInt(gui_config.ascii, int(bool(value)))

def add_tool(toolbar, id, label, ico):
    tbsize = toolbar.GetToolBitmapSize()
    bmp = get_icon_resource_bmp(ico, tbsize)
    return toolbar.AddTool(id, label, bmp, shortHelp = label)

class gui_frame(wx.Frame):
    ID_CMD_EXIT = wx.ID_EXIT
    ID_CMD_OPEN = wx.ID_OPEN
    ID_CMD_EXPORT = 103
    ID_CMD_IMPORT = 104
    ID_CMD_DELETE = wx.ID_DELETE
    ID_CMD_ASCII = 106
    
    def message_box(self, message, caption = "mymc", style = wx.OK, x = -1, y = -1):
        return wx.MessageBox(message, caption, style, self, x, y)

    def error_box(self, msg):
        return self.message_box(msg, "Error", wx.OK | wx.ICON_ERROR)
        
    def mc_error(self, value, filename = None):
        if filename == None: filename = getattr(value, "filename", None)
        if filename == None: filename = self.mcname
        if filename == None: filename = "???"
        strerror = getattr(value, "strerror", None)
        if strerror == None: strerror = "unknown error"
        return self.error_box(filename + ": " + strerror)

    def __init__(self, parent, title, mcname = None):
        self.f = None
        self.mc = None
        self.mcname = None
        self.icon_win = None

        size = (750, 350) if has_opengl else (500, 350)
        wx.Frame.__init__(self, parent, wx.ID_ANY, title, size = size)
        self.Bind(wx.EVT_CLOSE, self.evt_close)

        self.config = gui_config()
        self.title = title
        self.SetIcons(get_icon_resource("mc4.ico"))

        bind_menu = (lambda handler, id: self.Bind(wx.EVT_MENU, handler, id=id))
        bind_menu(self.evt_cmd_exit, self.ID_CMD_EXIT)
        bind_menu(self.evt_cmd_open, self.ID_CMD_OPEN)
        bind_menu(self.evt_cmd_export, self.ID_CMD_EXPORT)
        bind_menu(self.evt_cmd_import, self.ID_CMD_IMPORT)
        bind_menu(self.evt_cmd_delete, self.ID_CMD_DELETE)
        bind_menu(self.evt_cmd_ascii, self.ID_CMD_ASCII)
        
        filemenu = wx.Menu()
        filemenu.Append(self.ID_CMD_OPEN, "&Open...", "Opens an existing PS2 memory card image.")
        filemenu.AppendSeparator()
        self.export_menu_item = filemenu.Append(self.ID_CMD_EXPORT, "&Export...", "Export a save file from this image.")
        self.import_menu_item = filemenu.Append(self.ID_CMD_IMPORT, "&Import...", "Import a save file into this image.")
        self.delete_menu_item = filemenu.Append(self.ID_CMD_DELETE, "&Delete")
        filemenu.AppendSeparator()
        filemenu.Append(self.ID_CMD_EXIT, "E&xit")

        optionmenu = wx.Menu()
        self.ascii_menu_item = optionmenu.AppendCheckItem(self.ID_CMD_ASCII, "&ASCII Descriptions", "Show descriptions in ASCII instead of Shift-JIS")

        self.Bind(wx.EVT_MENU_OPEN, self.evt_menu_open)

        self.CreateToolBar(wx.TB_HORIZONTAL)
        self.toolbar = toolbar = self.GetToolBar()
        tbsize = (32, 32)
        toolbar.SetToolBitmapSize(tbsize)
        add_tool(toolbar, self.ID_CMD_OPEN, "Open", "mc2.ico")
        toolbar.AddSeparator()
        add_tool(toolbar, self.ID_CMD_IMPORT, "Import", "mc5b.ico")
        add_tool(toolbar, self.ID_CMD_EXPORT, "Export", "mc6a.ico")
        toolbar.Realize()

        self.statusbar = self.CreateStatusBar(2, style = wx.STB_SIZEGRIP)
        self.statusbar.SetStatusWidths([-2, -1])
        
        panel = wx.Panel(self, wx.ID_ANY, (0, 0))

        self.dirlist = dirlist_control(panel, self.evt_dirlist_item_focused, self.evt_dirlist_select, self.config)
        if mcname != None: self.open_mc(mcname)
        else: self.refresh()

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.dirlist, 2, wx.EXPAND)
        sizer.AddSpacer(5)

        icon_win = icon_window(panel)
        if icon_win.failed:
            icon_win.Destroy()
            icon_win = None
        self.icon_win = icon_win
        
        if icon_win == None:
            self.info1 = None
            self.info2 = None
        else:
            self.icon_menu = icon_menu = wx.Menu()
            icon_win.append_menu_options(self, icon_menu)
            optionmenu.AppendSubMenu(icon_menu, "Icon Window")
            title_style =  wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE
            
            self.info1 = wx.StaticText(panel, -1, "", style = title_style)
            self.info2 = wx.StaticText(panel, -1, "", style = title_style)

            info_sizer = wx.BoxSizer(wx.VERTICAL)
            info_sizer.Add(self.info1, 0, wx.EXPAND)
            info_sizer.Add(self.info2, 0, wx.EXPAND)
            info_sizer.AddSpacer(5)
            info_sizer.Add(icon_win, 1, wx.EXPAND)

            sizer.Add(info_sizer, 1, wx.EXPAND | wx.ALL, border = 5)

        menubar = wx.MenuBar()
        menubar.Append(filemenu, "&File")
        menubar.Append(optionmenu, "&Options")
        self.SetMenuBar(menubar)
        
        panel.SetSizer(sizer)
        panel.SetAutoLayout(True)
        sizer.Fit(panel)
        self.Show(True)

        if self.mc == None: self.evt_cmd_open()

    def _close_mc(self):
        if self.mc != None:
            try: self.mc.close()
            except EnvironmentError as value: self.mc_error(value)
            self.mc = None
        if self.f != None:
            try: self.f.close()
            except EnvironmentError as value: self.mc_error(value)
            self.f = None
        self.mcname = None
        
    def refresh(self):
        try: self.dirlist.update(self.mc)
        except EnvironmentError as value:
            self.mc_error(value)
            self._close_mc()
            self.dirlist.update(None)

        mc = self.mc
        self.toolbar.EnableTool(self.ID_CMD_IMPORT, mc != None)
        self.toolbar.EnableTool(self.ID_CMD_EXPORT, False)

        if mc == None: status = "No memory card image"
        else:
            free = mc.get_free_space() // 1024
            limit = mc.get_allocatable_space() // 1024
            status = "%dK of %dK free" % (free, limit)
        self.statusbar.SetStatusText(status, 1)

    def open_mc(self, filename):
        self._close_mc()
        self.statusbar.SetStatusText("", 1)
        if self.icon_win != None: self.icon_win.load_icon(None, None)
        
        f = None
        try:
            f = open(filename, "r+b")
            mc = ps2mc.ps2mc(f)
        except EnvironmentError as value:
            if f != None: f.close()
            self.mc_error(value, filename)
            self.SetTitle(self.title)
            self.refresh()
            return

        self.f = f
        self.mc = mc
        self.mcname = filename
        self.SetTitle(filename + " - " + self.title)
        self.refresh()

    def evt_menu_open(self, event):
        self.import_menu_item.Enable(self.mc != None)
        selected = self.mc != None and len(self.dirlist.selected) > 0
        self.export_menu_item.Enable(selected)
        self.delete_menu_item.Enable(selected)
        self.ascii_menu_item.Check(self.config.get_ascii())
        if self.icon_win != None: self.icon_win.update_menu(self.icon_menu)

    def evt_dirlist_item_focused(self, event):
        if self.icon_win == None: return
        mc = self.mc
        i = event.GetData()
        (ent, icon_sys, size, title) = self.dirlist.dirtable[i]
        
        try:
            t0 = title[0].decode('utf-8', 'ignore') if isinstance(title[0], bytes) else str(title[0])
            t1 = title[1].decode('utf-8', 'ignore') if isinstance(title[1], bytes) else str(title[1])
            self.info1.SetLabel(t0)
            self.info2.SetLabel(t1)
        except Exception:
            self.info1.SetLabel("Unknown")
            self.info2.SetLabel("Unknown")

        a = ps2save.unpack_icon_sys(icon_sys)
        try:
            dir_str = ent[8].decode('utf-8', 'ignore') if isinstance(ent[8], bytes) else str(ent[8])
            mc.chdir("/" + dir_str)
            icon_filename = a[15].decode('utf-8', 'ignore') if isinstance(a[15], bytes) else str(a[15])
            f = mc.open(icon_filename, "rb")
            try: icon = f.read()
            finally: f.close()
        except EnvironmentError as value:
            print("icon failed to load", value)
            self.icon_win.load_icon(None, None)
            return

        self.icon_win.load_icon(icon_sys, icon)

    def evt_dirlist_select(self, event):
        self.toolbar.EnableTool(self.ID_CMD_IMPORT, self.mc != None)
        self.toolbar.EnableTool(self.ID_CMD_EXPORT, len(self.dirlist.selected) > 0)

    def evt_cmd_open(self, event = None):
        fn = wx.FileSelector("Open Memory Card Image", self.config.get_memcard_dir(""), "Mcd001.ps2", "ps2", "PS2 Memory Cards (*.ps2)|*.ps2|All files|*", wx.FD_FILE_MUST_EXIST | wx.FD_OPEN, self)
        if fn == "": return
        self.open_mc(fn)
        if self.mc != None:
            dirname = os.path.dirname(fn)
            if os.path.isabs(dirname):
                self.config.set_memcard_dir(dirname)

    def evt_cmd_export(self, event):
        mc = self.mc
        if mc == None: return
        selected = self.dirlist.selected
        dirtable = self.dirlist.dirtable
        sfiles = []
        for i in selected:
            dir_str = dirtable[i][0][8].decode('utf-8', 'ignore') if isinstance(dirtable[i][0][8], bytes) else str(dirtable[i][0][8])
            try:
                sf = mc.export_save_file("/" + dir_str)
                longname = ps2save.make_longname(dir_str, sf)
                sfiles.append((dir_str, sf, longname))
            except EnvironmentError as value:
                self.mc_error(value, dir_str)

        if len(sfiles) == 0: return
        dir_path = self.config.get_savefile_dir("")
        if len(selected) == 1:
            (dirname, sf, longname) = sfiles[0]
            fn = wx.FileSelector("Export " + dirname, dir_path, longname, "psu", "EMS save file (*.psu)|*.psu|MAXDrive save file (*.max)|*.max", (wx.FD_OVERWRITE_PROMPT | wx.FD_SAVE), self)
            if fn == "": return
            try:
                f = open(fn, "wb")
                try:
                    if fn.endswith(".max"): sf.save_max_drive(f)
                    else: sf.save_ems(f)
                finally: f.close()
            except EnvironmentError as value:
                self.mc_error(value, fn)
                return
            dir_path = os.path.dirname(fn)
            if os.path.isabs(dir_path): self.config.set_savefile_dir(dir_path)
            self.message_box("Exported " + fn + " successfully.")
            return
        
        dir_path = wx.DirSelector("Export Save Files", dir_path, parent = self)
        if dir_path == "": return
        count = 0
        for (dirname, sf, longname) in sfiles:
            fn = os.path.join(dir_path, longname) + ".psu"
            try:
                f = open(fn, "wb")
                sf.save_ems(f)
                f.close()
                count += 1
            except EnvironmentError as value: self.mc_error(value, fn)
        if count > 0:
            if os.path.isabs(dir_path): self.config.set_savefile_dir(dir_path)
            self.message_box("Exported %d file(s) successfully." % count)
            
    def _do_import(self, fn):
        sf = ps2save.ps2_save_file()
        f = open(fn, "rb")
        try:
            ft = ps2save.detect_file_type(f)
            f.seek(0)
            if ft == "max": sf.load_max_drive(f)
            elif ft == "psu": sf.load_ems(f)
            elif ft == "cbs": sf.load_codebreaker(f)
            elif ft == "sps": sf.load_sharkport(f)
            elif ft == "npo":
                self.error_box(fn + ": nPort saves are not supported.")
                return
            else:
                self.error_box(fn + ": Save file format not recognized.")
                return
        finally: f.close()
        if not self.mc.import_save_file(sf, True):
            self.error_box(fn + ": Save file already present.")
        
    def evt_cmd_import(self, event):
        if self.mc == None: return
        dir_path = self.config.get_savefile_dir("")
        fd = wx.FileDialog(self, "Import Save File", dir_path, wildcard = ("PS2 save files (*.cbs;*.psu;*.max;*.sps;*.xps)|*.cbs;*.psu;*.max;*.sps;*.xps|All files|*"), style = (wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST))
        if fd == None: return
        r = fd.ShowModal()
        if r == wx.ID_CANCEL: return
        success = None
        for fn in fd.GetPaths():
            try:
                self._do_import(fn)
                success = fn
            except EnvironmentError as value: self.mc_error(value, fn)
        if success != None:
            dir_path = os.path.dirname(success)
            if os.path.isabs(dir_path): self.config.set_savefile_dir(dir_path)
        self.refresh()

    def evt_cmd_delete(self, event):
        mc = self.mc
        if mc == None: return
        selected = self.dirlist.selected
        dirtable = self.dirlist.dirtable
        
        dirnames = []
        for i in selected:
            n = dirtable[i][0][8]
            dirnames.append(n.decode('utf-8', 'ignore') if isinstance(n, bytes) else str(n))
            
        if len(selected) == 1:
            title = dirtable[list(selected)[0]][3]
            s = dirnames[0] + " (" + single_title(title) + ")"
        else:
            s = ", ".join(dirnames)
            if len(s) > 200: s = s[:200] + "..."
        r = self.message_box("Are you sure you want to delete " + s + "?", "Delete Save File Confirmation", wx.YES_NO)
        if r != wx.YES: return
        for dn in dirnames:
            try: mc.rmdir("/" + dn)
            except EnvironmentError as value: self.mc_error(value, dn)
        mc.check()
        self.refresh()

    def evt_cmd_ascii(self, event):
        self.config.set_ascii(not self.config.get_ascii())
        self.refresh()
        
    def evt_cmd_exit(self, event): self.Close(True)
    def evt_close(self, event):
        self._close_mc()
        self.Destroy()
        
def run(filename = None):
    wx_app = wx.App()
    frame = gui_frame(None, "mymc", filename)
    return wx_app.MainLoop()
    
if __name__ == "__main__":
    run()