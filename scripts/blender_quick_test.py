import bpy, math, os

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 360
scene.render.resolution_y = 640
scene.render.filepath = os.path.join(os.path.dirname(__file__), "..", "output", "run_test", "satisfying", "blender_frame")
scene.render.image_settings.file_format = 'PNG'
scene.frame_end = 1

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.95, 0.95, 0.95, 1)

mat_ext = bpy.data.materials.new("GlassExt")
mat_ext.use_nodes = True
n = mat_ext.node_tree.nodes; n.clear()
o = n.new("ShaderNodeOutputMaterial")
g = n.new("ShaderNodeBsdfGlass")
g.inputs["Color"].default_value = (0.1, 0.6, 0.15, 1)
g.inputs["Roughness"].default_value = 0.05
mat_ext.node_tree.links.new(g.outputs[0], o.inputs[0])

mat_int = bpy.data.materials.new("GlassInt")
mat_int.use_nodes = True
n = mat_int.node_tree.nodes; n.clear()
o = n.new("ShaderNodeOutputMaterial")
g = n.new("ShaderNodeBsdfGlass")
g.inputs["Color"].default_value = (0.8, 0.1, 0.15, 1)
mat_int.node_tree.links.new(g.outputs[0], o.inputs[0])

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.15))
board = bpy.context.active_object
board.scale = (2, 1.5, 0.1)

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(-0.3, 0, 0.35))
wl = bpy.context.active_object
wl.scale = (0.5, 0.8, 0.7)
wl.data.materials.append(mat_ext)

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0.3, 0, 0.35))
wr = bpy.context.active_object
wr.scale = (0.5, 0.8, 0.7)
wr.data.materials.append(mat_ext)

bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=0.02, location=(0, 0, 0.35))
interior = bpy.context.active_object
interior.scale = (1, 0.7, 1)
interior.rotation_euler = (0, math.radians(90), 0)
interior.data.materials.append(mat_int)

bpy.ops.object.camera_add(location=(2.5, -2, 1.2))
cam = bpy.context.active_object
scene.camera = cam
c = cam.constraints.new('TRACK_TO')
c.target = wl
c.track_axis = 'TRACK_NEGATIVE_Z'
c.up_axis = 'UP_Y'
cam.data.lens = 85

bpy.ops.object.light_add(type='AREA', location=(2, -1, 3))
bpy.context.active_object.data.energy = 200
bpy.ops.object.light_add(type='AREA', location=(0, 2, 2))
bpy.context.active_object.data.energy = 150

print("Rendering...")
bpy.ops.render.render(write_still=True)
print("DONE")
