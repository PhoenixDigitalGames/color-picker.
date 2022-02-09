import json, os, bpy

def upload_material(name, mdat):
    # Get material
    mat = bpy.data.materials.get(name)
    if mat is None:
        # create material
        mat = bpy.data.materials.new(name=name)
        bpy.data.materials.create_gpencil_data(mat)
    elif not mat.is_grease_pencil:
        print(f"Error: Material {name} exists and is not GP.")
        return False

    # Setting up material settings
    m = mat.grease_pencil
    count_ignored = 0
    for k,v in mdat.items():
        if not hasattr(m, k):
            print("Attr ignored ", k)
            count_ignored += 1 
            continue
        setattr(m, k, v)
    
    gpmatit = bpy.context.scene.gpmatpalette.materials.add()
    gpmatit.mat_name = name

    return True

def upload_image(imdata, fpath):
    if not "path" in imdata:
        return False
    impath = imdata["path"]
    if ("relative" in imdata) and (imdata["relative"]):
        impath = os.path.dirname(fpath) + "/" + impath
    print("Image full path : ", impath)
    
    bpy.context.scene.gpmatpalette.image = impath
    
    return True

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

        if not os.path.isfile(fpt):
            print("Error : {} path not found".format(fpt))
            return {'CANCELLED'}

        fnm = os.path.basename(fpt)
        ext = fnm.split(os.extsep)
        
        if (len(ext) < 2) or (ext[-1] != "json"):
            print("Error : {} is not a json file".format(fnm))
            return {'CANCELLED'}
        
        ifl = open(fpt, 'r')
        ctn = json.load(ifl)
        ifl.close()
        
        if not "materials" in ctn :
            print("Error : {} does not contain any material".format(fnm))
            return {'CANCELLED'}

        bpy.context.scene.gpmatpalette.clear()
        palette = ctn["materials"]
        for name,mat in palette.items():
            print(f"Material {name}")
            upload_material(name, mat)

        if "image" in ctn:
            upload_image(ctn["image"], fpt)

        # Update data in user preferences
        prefs = context.preferences.addons[__package__].preferences
        if prefs is None : 
            self.report({'WARNING'}, "Could not load user preferences")
        else:
            prefs.json_fpath = fpt

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}