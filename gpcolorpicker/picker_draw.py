# GPU drawing related functions
import blf, gpu
from gpu_extras.batch import batch_for_shader
import numpy as np

''' Common GLSL functions used in many shaders 
    Mostly creates geometric primitives with anti-aliasing
'''
common_libsh='''
    float aa_circle(float rds, float dst, float eps){
        return smoothstep(rds+eps, rds-eps, dst);
    }        

    float aa_contour(float rds, float wdt, float dst, float eps){
        float a0 = aa_circle(rds+wdt/2., dst, eps);
        float a1 = aa_circle(rds-wdt/2., dst, eps);
        return a0*(1-a1);
    }     

    float aa_donut(float rds0, float rds1, float dst, float eps){
        float a0 = aa_circle(rds0, dst, eps);
        float a1 = aa_circle(rds1, dst, eps);
        return a0*(1-a1);
    }

    float aa_seg( vec2 s0, vec2 s1, vec2 p, float wdt, float eps){
        float lgt = length(s0-s1);
        vec2 udr = (s1-s0)/lgt;
        vec2 lp = p - s0;
        float prj = dot(lp, udr);
        float alpha = 1.;

        alpha *= smoothstep(-eps, eps, prj);  
        alpha *= smoothstep(lgt+eps, lgt-eps, prj);  
        if( alpha == 0.){
            return 0.;
        }
        
        float d = length(prj*udr - lp);
        return alpha*smoothstep(wdt+eps, wdt-eps, d);
    }

    vec4 alpha_compose(vec4 A, vec4 B){
        /* A over B */
        vec4 color = vec4(0.);
        color.a = A.a + B.a*(1.- A.a);
        if( color.a == 0. ){
            return color;
        }
        color.rgb = (A.rgb * A.a + B.rgb * B.a * (1 - A.a))/(color.a);
        return color;
    }

    bool in_interval(float x, float a, float b){
        return (x >= a) && (x <= b);
    }
'''

''' Useful function to set an array of float* as shader uniform 
    * Actually, the array could contain either float, vec2, vec3 or vec4 elements
'''
def set_uniform_vector_float(shader, data_, var_name):
    if(len(data_) == 0):
        return
    data = data_
    if isinstance(data[0],float):
        data = [ [x] for x in data_ ]
    dim = [len(data),len(data[0])]
    buf = gpu.types.Buffer('FLOAT', dim, data)
    loc = shader.uniform_from_name(var_name)
    shader.uniform_vector_float(loc, buf, dim[1], dim[0])

''' Useful function to load an image data as GPU texture to be used in a shader'''
def load_gpu_texture(image):
    if not image:
        return None 

    gpu_tex = gpu.texture.from_image(image)
    if (gpu_tex.height > 1) or (gpu_tex.width > 1):
        return gpu_tex
        
    return None

''' --- Drawing functions --- '''

''' Sets up a shader program to draw an image in the dimensions given in the settings '''
def setup_shader(op, settings, fragsh, libsh=common_libsh):
    vsh = '''            
        uniform mat4 modelViewProjectionMatrix;
        uniform float dimension;
        uniform vec2 origin;
        
        in vec2 pos;
        out vec2 lpos;
        out vec2 uv;

        void main()
        {
          gl_Position = modelViewProjectionMatrix*vec4(dimension*pos+origin, 0.0, 1.0);
          lpos = dimension*pos;
          uv = (pos+1)*0.5;
        }
    '''
    shader = gpu.types.GPUShader(vsh, fragsh, libcode=libsh)

        # Simple screen quad
    dimension = settings.mat_centers_radius + 2*settings.mat_radius
    vdata = np.asarray(((-1, 1), (-1, -1),(1, -1), (1, 1)))
    vertices = np.ndarray.tolist(vdata)        
    indices = ((0, 1, 2), (0, 2, 3))
    
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
    shader.bind() 
    
        # Set up uniform variables
    matrix = gpu.matrix.get_projection_matrix()*gpu.matrix.get_model_view_matrix()
    shader.uniform_float("modelViewProjectionMatrix", matrix)     
    shader.uniform_float("dimension",dimension)
    shader.uniform_float("origin", op.origin)

    return shader,batch 

''' In the case of "from active" material mode, or if there is no image in palette
    Draws a simple pie circle in the colors and scale given by the settings
'''
def draw_pie_circle(op, settings): 
    pie_circle_fsh = '''
        #define PI 3.1415926538
        uniform vec4 circle_color;
        uniform float inner_radius;
        uniform float outer_radius;
        uniform vec4 line_color;
        uniform float line_width;
        uniform float aa_eps;

        in vec2 lpos;
        in vec2 uv;
        out vec4 fragColor;   

        void main()
        {                    
            float d = length(lpos);
            fragColor = vec4(0.);

            vec4 fill_color_ = circle_color;
            vec4 stroke_color = line_color;

            fill_color_.a *= aa_donut(outer_radius, inner_radius, d, aa_eps);
            stroke_color.a *= aa_contour(inner_radius, line_width, d, aa_eps);

            vec4 fragColor_main = alpha_compose(stroke_color, fill_color_);     
            fragColor = alpha_compose(fragColor_main, fragColor);
        }
    '''    

    shader, batch = setup_shader(op, settings, pie_circle_fsh)
    
    shader.uniform_float("circle_color", settings.mc_fill_color)
    shader.uniform_float("inner_radius", settings.mc_inner_radius)
    shader.uniform_float("outer_radius", settings.mc_outer_radius)
    shader.uniform_float("line_color", settings.mc_line_color)
    shader.uniform_float("line_width", settings.mc_line_width)  
    shader.uniform_float("aa_eps", settings.anti_aliasing_eps)
    
    batch.draw(shader) 

''' Draws all the material previews and their picklines '''
def draw_materials(op, cache, settings):
    materials_fsh = '''
    #define PI 3.1415926538
    uniform float selected_radius;
    uniform vec4 active_color;
    uniform float mat_radius;
    uniform float mat_line_width;
    uniform float mat_centers_radius;
    uniform int mat_nb;
    uniform int mat_selected;
    uniform int mat_active;
    uniform vec4 mat_fill_colors[__NMAT__];
    uniform vec4 mat_line_colors[__NMAT__];
    uniform float mat_thetas[__NMAT__];
    #ifdef _PICKLINES_
    uniform vec3 mat_picklines[__NPLM__];
    uniform float pickline_width;
    uniform vec4 pickline_color;
    #endif
    uniform float aa_eps;

    in vec2 lpos;
    in vec2 uv;
    out vec4 fragColor;            

    void main()
    {                    
        float d = length(lpos);
        fragColor = vec4(0.);


        #ifdef _PICKLINES_
        /* Pick lines */
        for(int k = 0; k < __NPLM__; ++k){
            int i = int(mat_picklines[k].z);
            bool is_selected = (i == mat_selected);

            float th_i = mat_thetas[i];
            float R = is_selected?(mat_centers_radius + selected_radius - mat_radius):mat_centers_radius;
            float radius = is_selected?selected_radius:mat_radius;

            float rds = (R-radius);
            vec2 s0 = rds*mat_picklines[k].xy;
            vec2 s1 = rds*vec2(cos(th_i), sin(th_i));

            vec4 fragColor_line = pickline_color;
            fragColor_line.a *= ((mat_selected >=0) && !is_selected)?0.3:1;
            fragColor_line.a *= aa_seg(s0, s1, lpos, pickline_width, aa_eps);

            fragColor = alpha_compose(fragColor, fragColor_line);
        }
        #endif

        /*    MATERIALS CIRCLES    */
        for(int i = 0; i < mat_nb; ++i){
            /* get color and if circle is currently selected */
            vec4 fill_color = mat_fill_colors[i];
            vec4 line_color = mat_line_colors[i];
            bool is_selected = (i == mat_selected);
            bool is_active = (i == mat_active);

            /* compute the center of circle */
            float th_i = mat_thetas[i];
            float R = is_selected?(mat_centers_radius + selected_radius - mat_radius):mat_centers_radius;
            vec2 ci = R*vec2(cos(th_i),sin(th_i));
            d = length(lpos-ci);     

            /* draw circle */
            float radius = is_selected?selected_radius:mat_radius;
            fill_color.a *= aa_circle(radius, d, aa_eps);
            line_color.a *= aa_contour(radius, mat_line_width, d, aa_eps);

            vec4 fragColor_mat = alpha_compose(line_color, fill_color);

            if( is_active ){
                vec4 act_color = active_color;
                float act_rds = mat_centers_radius + radius + mat_line_width*2.5;
                vec2 act_ctr = act_rds*vec2(cos(th_i),sin(th_i));
                float act_dst = length(lpos-act_ctr);
                act_color.a *= aa_circle(mat_line_width, act_dst, aa_eps);
                fragColor_mat = alpha_compose(act_color, fragColor_mat);
            }

            fragColor = alpha_compose(fragColor_mat, fragColor);
        }
    }
    '''     
    fsh = materials_fsh

    nmat = cache.mat_nb
    if nmat <= 0:
        return    
    
    nplm = cache.nb_max_picklines
    if nplm > 0:
        fsh = "#define _PICKLINES_" + fsh.replace("__NPLM__",str(nplm))

    fsh = fsh.replace("__NMAT__",str(nmat))

    shader, batch = setup_shader(op, settings, fsh)

    shader.uniform_float("selected_radius", settings.selected_radius)
    shader.uniform_float("active_color", settings.active_color)
    shader.uniform_float("mat_radius", settings.mat_radius)
    shader.uniform_float("mat_line_width", settings.mat_line_width)
    shader.uniform_float("mat_centers_radius", settings.mat_centers_radius)
    shader.uniform_float("aa_eps", settings.anti_aliasing_eps)
    if nplm > 0:
        shader.uniform_float("pickline_width", settings.pickline_width)
        shader.uniform_float("pickline_color", settings.mc_line_color)
    shader.uniform_int("mat_selected", op.mat_selected);   
    shader.uniform_int("mat_nb", nmat);    
    shader.uniform_int("mat_active", cache.mat_active);   
    
    set_uniform_vector_float(shader, cache.mat_fill_colors, "mat_fill_colors")
    set_uniform_vector_float(shader, cache.mat_line_colors, "mat_line_colors")
    set_uniform_vector_float(shader, cache.angles, "mat_thetas") 
    if nplm > 0:
        set_uniform_vector_float(shader, cache.get_picklines(), "mat_picklines")

    batch.draw(shader)

''' Draws the image of the palette in the middle of the icon '''
def draw_centered_texture(op, context, cache, settings):
    centered_tex_fsh = '''
        #define PI 3.1415926538
        uniform sampler2D tex;  
        uniform float rad_tex;
        uniform float aa_eps;

        in vec2 lpos;
        in vec2 uv;
        out vec4 fragColor;      

        void main()
        {          
            float aspect_ratio = textureSize(tex,0).x / float(textureSize(tex,0).y);
            float w = 2*rad_tex;
            float h = 2*rad_tex;
            if(aspect_ratio > 1){
                w *= aspect_ratio;
            }
            else{
                h *= aspect_ratio;
            }
            vec2 uv_tex = lpos/(vec2(w,h)) + vec2(0.5);

            float dst = length(lpos);
            fragColor = texture(tex,uv_tex);
            fragColor.a *= aa_circle(rad_tex, dst, aa_eps);
        }
    '''
    gpmp = context.scene.gpmatpalettes.active()
    sid = op.mat_selected
    if (gpmp.name == cache.pal_active) and \
         (sid == cache.mat_cached) :
        tx = cache.gpu_texture
    elif ( sid == -1 ) or ( not gpmp.materials[sid].image ):
        tx = load_gpu_texture(gpmp.image)
    else:
        tx = load_gpu_texture(gpmp.materials[sid].image) 
    
    if not tx:
        return

    rds = settings.tex_radius    
    shader, batch = setup_shader(op, settings, centered_tex_fsh)
    shader.uniform_sampler("tex",tx)
    shader.uniform_float("rad_tex",rds)    
    shader.uniform_float("aa_eps",settings.anti_aliasing_eps)    
    batch.draw(shader) 

    cache.gpu_tex = tx
    cache.mat_cached = sid
    cache.pal_active = gpmp.name

''' --- Writing functions --- '''

''' Useful function to write text centered in a circle of origin org, and of radius ird'''
def write_circle_centered(settings, org, ird, text):
    font_id = 1
    blf.color(font_id, *(settings.text_color))
    blf.size(font_id, settings.text_size, 72)
    blf.enable(font_id,blf.CLIPPING)
    
    dmin, dmax = org - ird, org + ird
    blf.clipping(font_id, dmin[0], dmin[1], dmax[0], dmax[1])
    
    txd = np.asarray(blf.dimensions(font_id, text))
    pos = org - 0.5*txd
    blf.position(font_id, pos[0], pos[1], 0)
    blf.draw(font_id, text)
    gpu.state.blend_set('ALPHA')   

''' Writes the name of the selected material '''
def write_selected_mat_name(op, cache, settings):
    txt = cache.materials[op.mat_selected].name
    org = op.origin + 0.5*op.region_dim
    org[1] = org[1] - (settings.mat_centers_radius+2*settings.mat_radius)
    org[1] = org[1] - settings.text_size
    ird = settings.mc_outer_radius
    write_circle_centered(settings, org, ird, txt)

''' Writes the name of the active palette '''
def write_active_palette(op, context, settings):
    plt = context.scene.gpmatpalettes.active()
    if not plt:
        return
    txt = plt.name
    org = op.origin + 0.5*op.region_dim
    org[1] = org[1] - (settings.mat_centers_radius+2*settings.mat_radius)
    ird = settings.mc_outer_radius
    write_circle_centered(settings, org, ird, txt)


''' Main Drawing function for the GP Color Picker'''
def draw_callback_px(op, context, cache, settings): 
    gpu.state.blend_set('ALPHA')   

    if op.mat_selected >= 0:
        write_selected_mat_name(op, cache, settings)
        
    if cache.use_gpu_texture():
        draw_centered_texture(op, context, cache, settings)
    else:
        draw_pie_circle(op, settings)

    draw_materials(op, cache, settings)  

    if cache.from_palette:
        write_active_palette(op, context, settings)

    # Reset blend mode
    gpu.state.blend_set('NONE')
    # op.check_time()
    