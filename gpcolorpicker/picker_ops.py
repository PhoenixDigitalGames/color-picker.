import bpy
import numpy as np
from . picker_draw import draw_callback_px
from . picker_settings import GPCOLORPICKER_settings
from . picker_interactions import get_selected_mat_id, CachedData
import time


### ----------------- Operator definition
class GPCOLORPICKER_OT_wheel(bpy.types.Operator):
    bl_idname = "gpencil.color_pick"
    bl_label = "GP Color Picker"  

    @classmethod
    def poll(cls, context):
        return  (context.area.type == 'VIEW_3D') and \
                (context.mode == 'PAINT_GPENCIL') and \
                (context.active_object is not None) and \
                (context.active_object.type == 'GPENCIL')


    def modal(self, context, event):
        context.area.tag_redraw()  

        def mat_selected_in_range():
            i = self.mat_selected
            return (i >= 0) and (i < self.cached_data.mat_nb)
        
        def set_active_material(ob, stg_id, ob_id):
            ob.active_material_index = ob_id

            if not self.cached_data.from_palette:
                return True
            
            gpmp = context.scene.gpmatpalettes.active()
            gpmt = gpmp.materials[stg_id]
            if not gpmt.layer:
                return True

            if not gpmt.layer in ob.data.layers:
                bpy.ops.gpencil.layer_add()
                ob.data.layers.active.info = gpmt.layer
            else:
                ob.data.layers.active = ob.data.layers[gpmt.layer]

            return True

        def validate_selection():
            if not mat_selected_in_range():
                return True

            sid = self.mat_selected
            if not self.cached_data.from_palette:
                return set_active_material(self.active_obj, sid, sid)
            
            ob_mat = self.active_obj.data.materials                
            mat = self.cached_data.materials[sid]
            oid = ob_mat.find(mat.name)

            if oid >= 0:
                # Found material in current object
                return set_active_material(self.active_obj, sid, oid)
            
            if self.settings.mat_assign:
                # Assigning new material to current object
                oid = len(ob_mat)
                ob_mat.append(mat)
                return set_active_material(self.active_obj, sid, oid)

            self.report({'WARNING'}, 'Active object does not contain material')
            return False

        if event.type == 'MOUSEMOVE':
            self.mat_selected = get_selected_mat_id(event,self.region_dim, self.origin, self.cached_data.mat_nb, \
                                             self.settings.interaction_radius, self.cached_data.angles)
        
        elif (event.type == self.settings.switch_key) and (event.value == 'PRESS'):
            dir = 1
            if event.shift:
                dir = -1
            bpy.context.scene.gpmatpalettes.next(dir)
            self.cached_data.refresh()
            self.mat_selected = get_selected_mat_id(event,self.region_dim, self.origin, self.cached_data.mat_nb, \
                                             self.settings.interaction_radius, self.cached_data.angles)


        elif ((event.type == self.invoke_key) \
                and (event.value == 'RELEASE') and (self.mat_selected != -1)) \
                    or (event.type == 'LEFTMOUSE'):
            if validate_selection():   
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                bpy.ops.ed.undo_push()
                return {'FINISHED'}                

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def check_time(self):
        if self.timeout:
            return
        print("Timer : ", time.time() - self.tsart)
        self.timeout = True

    def invoke(self, context, event):  
        self.tsart = time.time()
        self.timeout = False

        pname = (__package__).split('.')[0]
        prefs = context.preferences.addons[pname].preferences
        if prefs is None : 
            self.report({'WARNING'}, "Could not load user preferences, running with default values")
        self.settings = GPCOLORPICKER_settings(prefs)  

        gpmp = context.scene.gpmatpalettes.active()
        if (not self.settings.mat_from_active) and (not gpmp):
            self.report({'WARNING'}, "No active palette")
            return {'CANCELLED'}

        # Get event related data
        self.invoke_key = event.type
        self.region_dim = np.asarray([context.region.width,context.region.height])
        self.origin = np.asarray([event.mouse_region_x,event.mouse_region_y]) - 0.5*self.region_dim  

        self.mat_selected = -1
        self.active_obj = context.active_object

        # Init Cached Data
        self.cached_data = CachedData(not self.settings.mat_from_active)
        if self.cached_data.mat_nb == 0:
            self.report({'WARNING'}, "No material to pick")

        # Setting handlers
        mhandle = context.window_manager.modal_handler_add(self)
        if not mhandle:
            return {'CANCELLED'}  

        self._handle = context.space_data.draw_handler_add(draw_callback_px, (self,context,self.cached_data,self.settings), \
                                                        'WINDOW', 'POST_PIXEL')
        return {'RUNNING_MODAL'}    
