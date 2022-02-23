import json, os, bpy, gpu, math
from posixpath import relpath
from . palette_props import GPMatPalette

def srgb_to_linearrgb(c):
    '''from https://blender.stackexchange.com/a/158902/4979'''
    if   c < 0:       return 0
    elif c < 0.04045: return c/12.92
    else:             return ((c+0.055)/1.055)**2.4

def hex2rgba(hex, alpha):
    '''from https://blender.stackexchange.com/a/158902/4979'''
    h = hex
    if type(h) is str:
        h = int(h, 16)
    r = (h & 0xff0000) >> 16
    g = (h & 0x00ff00) >> 8
    b = (h & 0x0000ff)
    return tuple([srgb_to_linearrgb(c/0xff) for c in (r,g,b)] + [alpha])

def upload_material(name, mdat):
    # Get material
    mat = bpy.data.materials.get(name)
    if mat is None:
        # create material
        mat = bpy.data.materials.new(name=name)
        mat.use_fake_user = True
        bpy.data.materials.create_gpencil_data(mat)
    elif not mat.is_grease_pencil:
        print(f"Error: Material {name} exists and is not GP.")
        return False

    # Setting up material settings
    m = mat.grease_pencil
    for k,v in mdat.items():
        if not hasattr(m, k):
            continue
        if (k.find("color") >= 0)  \
            and isinstance(v[0], str):
                setattr(m, k, hex2rgba(v[0],v[1]))
                continue
        setattr(m, k, v)

    return True

def upload_palette(pname, data, fpt, palette):
    is_relative_path = False
    fdir = ""
    if ("image" in data) and ("path" in data["image"]):
        im_data = data["image"]
        is_relative_path = ("relative" in im_data) and (im_data["relative"])
        if is_relative_path:
            fdir = os.path.dirname(fpt)
        already_exists = (palette.image.path == im_data["path"])
        palette.image.load(im_data["path"], fdir, already_exists)

    hasImage = not (palette.image is None)

    for name,mat_data in data["materials"].items():
        if not upload_material(name, mat_data):
            continue
        
        if not name in palette.materials:
            gpmatit = palette.materials.add()
            gpmatit.name = name
        else:
            gpmatit = palette.materials[name]

        if "position" in mat_data.keys():
            def posdeg2rad(deg):
                rad = deg*math.pi/180.
                while rad < 0:
                    rad += 2*math.pi
                return rad
            gpmatit.custom_angle = posdeg2rad(mat_data["position"])
        
        if hasImage and ("image" in mat_data.keys()):
            already_exists = (gpmatit.image.path == mat_data["image"])
            gpmatit.image.load(mat_data["image"], fdir, already_exists)

        if "layer" in mat_data.keys():
            gpmatit.layer = mat_data["layer"]
    
    if len(palette.materials) == 0:
        print("No materials in palette. Aborting upload")
        return None
    
    palette.name = pname
    palette.source_path = fpt

    return palette

def parseJSONFile(json_file, palette_names=()):
    if not os.path.isfile(json_file):
        print("Error : {} path not found".format(json_file))
        return {'CANCELLED'}

    fnm = os.path.basename(json_file)
    ext = fnm.split(os.extsep)
    
    if (len(ext) < 2) or (ext[-1] != "json"):
        print("Error : {} is not a json file".format(fnm))
        return {'CANCELLED'}
    
    ifl = open(json_file, 'r')
    data = json.load(ifl)
    ifl.close()

    gpmatpalettes = bpy.context.scene.gpmatpalettes
    palettes = gpmatpalettes.palettes
    # Parse JSON
    for pname, pdata in data.items():
        if (len(palette_names) > 0) and (not pname in palette_names):
            continue

        if not pname in palettes:
            palette = palettes.add()
            ind = len(palettes)-1
        else:
            palette = palettes[pname]
            ind = palettes.find(pname)

        upload_palette(pname, pdata, json_file, palette)

        if not palette:
            print("Nothing found in palette ", pname)
            continue
        gpmatpalettes.active_index = ind

variables_notex = ["alignment_mode", "alignment_rotation","color","fill_color","fill_style","flip","ghost", \
            "gradient_type","hide","lock","mix_color", "mix_factor", "mix_stroke_factor", "mode", "pass_index", "pixel_size", \
            "show_fill", "show_stroke", "stroke_image", "stroke_style","use_fill_holdout", "use_overlap_strokes", "use_stroke_holdout"]

def get_material_data(mat):
    def parse_attr(attr):
        dtp = [int, float, bool, str]
        if (attr is None) or any([isinstance(attr, t) for t in dtp]):
            return attr
        return [attr[k] for k in range(len(attr))]

    mdat = { v:parse_attr(getattr(mat,v)) for v in variables_notex }

    return mdat

def get_palettes_content():
    gpmp = bpy.context.scene.gpmatpalettes.palettes
    pal_dct = {}

    for pname,pdata in gpmp.items():
        pal_dct[pname] = {}
        dat_mats = {m.name:m.grease_pencil for m in bpy.data.materials if m.is_grease_pencil}

        if not pdata.image.isempty():
            # todo : deal with relative and absolute path in a better way
            imname = os.path.basename(pdata.image.path)
            relpath = True
            pal_dct[pname]["image"] = {"path":imname, "relative":relpath}
        
        pal_dct[pname]["materials"] = {}
        mat_dct = pal_dct[pname]["materials"]
        for mname, mdata in pdata.materials.items(): 
            mat_dct[mname] = get_material_data(dat_mats[mname])

            if mdata.custom_angle >= 0:
                mat_dct[mname]["position"] = mdata.custom_angle*180/math.pi

            if not mdata.image.isempty():
                mat_dct[mname]["image"] = os.path.basename(mdata.image.path)

            if mdata.layer:
                mat_dct[mname]["layer"] = mdata.layer
    return pal_dct


### ----------------- Operator definition
class GPCOLORPICKER_OT_getJSONFile(bpy.types.Operator):
    bl_idname = "gpencil.file_load"
    bl_label = "Load File"    

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context): 
        fpt = self.filepath       

        parseJSONFile(fpt)

        # Update data in user preferences
        pname = (__package__).split('.')[0]
        prefs = context.preferences.addons[pname].preferences
        if prefs is None : 
            self.report({'WARNING'}, "Could not load user preferences")
        else:
            prefs.json_fpath = fpt

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
class GPCOLORPICKER_OT_exportPalette(bpy.types.Operator):
    bl_idname = "scene.export_palette"
    bl_label = "Export Palette"    

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @classmethod
    def poll(cls, context):
        return (context.scene.gpmatpalettes.active())

    def execute(self, context): 
        fpt = self.filepath            
        data = get_palettes_content()
        # Directly from dictionary
        with open(fpt, 'w') as outfile:
            json.dump(data, outfile, indent=4)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
class GPCOLORPICKER_OT_removePalette(bpy.types.Operator):
    bl_idname = "scene.remove_palette"
    bl_label = "Remove GP Palette"

    palette_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context): 
        gpmp = context.scene.gpmatpalettes
        npal = len(gpmp.palettes)
        if (self.palette_index < 0) or (self.palette_index >= npal):
            return {'CANCELLED'}

        active_ind = gpmp.active_index

        pal = gpmp.palettes[self.palette_index]
        pal.clear()
        gpmp.palettes.remove(self.palette_index)

        if active_ind == npal-1:
            gpmp.active_index = npal-2
        elif active_ind == self.palette_index:
            gpmp.next()

        return {'FINISHED'}


class GPCOLORPICKER_OT_reloadPalette(bpy.types.Operator):
    bl_idname = "scene.reload_palette"
    bl_label = "Reload GP Palette"

    palette_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context): 
        gpmp = context.scene.gpmatpalettes
        npal = len(gpmp.palettes)
        if (self.palette_index < 0) or (self.palette_index >= npal):
            return {'CANCELLED'}

        pal = gpmp.palettes[self.palette_index]
        pal.clear()

        fpath = gpmp.palettes[self.palette_index].source_path
        pname = gpmp.palettes[self.palette_index].name

        parseJSONFile(fpath, palette_names=(pname))

        return {'FINISHED'}

class GPCOLORPICKER_OT_togglePaletteVisibility(bpy.types.Operator):
    bl_idname = "scene.toggle_pal_visibility"
    bl_label= "Toggle Palette Visibility"

    palette_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context): 
        gpmp = context.scene.gpmatpalettes
        npal = len(gpmp.palettes)
        if (self.palette_index < 0) or (self.palette_index >= npal):
            return {'CANCELLED'}

        pal = gpmp.palettes[self.palette_index]
        pal.visible = not pal.visible

        if gpmp.active_index == self.palette_index:
            gpmp.next()

        return {'FINISHED'}

classes = [GPCOLORPICKER_OT_getJSONFile, \
            GPCOLORPICKER_OT_exportPalette, \
            GPCOLORPICKER_OT_removePalette, \
            GPCOLORPICKER_OT_reloadPalette, \
            GPCOLORPICKER_OT_togglePaletteVisibility]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)