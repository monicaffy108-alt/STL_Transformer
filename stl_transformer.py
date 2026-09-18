"""
STL Transformer - Blender Addon
Batch convert STL files to GLB and OBJ formats with automatic color schemes.
Supports URDF-based assembly to export complete models with correct positioning.

Author: [Your Name]
License: MIT
"""

bl_info = {
    "name": "STL Transformer",
    "author": "[Your Name]",
    "version": (2, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar (N) > STL Transformer",
    "description": "Batch convert STL to GLB and OBJ, or assemble URDF into complete models",
    "category": "Import-Export",
}

import bpy
import os
import math
import traceback
import xml.etree.ElementTree as ET
from mathutils import Matrix, Vector

COLOR_SCHEMES = {
    "light_blue": {
        "body":  (0.55, 0.68, 0.88, 1.0),
        "joint": (0.25, 0.28, 0.35, 1.0),
        "grip":  (0.06, 0.06, 0.08, 1.0),
        "metal": (0.65, 0.67, 0.72, 1.0),
    },
    "white": {
        "body":  (0.95, 0.95, 0.93, 1.0),
        "joint": (0.22, 0.24, 0.28, 1.0),
        "grip":  (0.06, 0.06, 0.08, 1.0),
        "metal": (0.65, 0.67, 0.72, 1.0),
    },
    "beige": {
        "body":  (0.85, 0.74, 0.58, 1.0),
        "joint": (0.22, 0.24, 0.28, 1.0),
        "grip":  (0.06, 0.06, 0.08, 1.0),
        "metal": (0.65, 0.67, 0.72, 1.0),
    },
    "robotic": {
        "body":  (0.28, 0.30, 0.34, 1.0),
        "joint": (0.15, 0.16, 0.19, 1.0),
        "grip":  (0.06, 0.06, 0.08, 1.0),
        "metal": (0.55, 0.57, 0.60, 1.0),
    },
}


def get_part_type(filename):
    name = filename.lower()
    if "hand_base" in name or "palm" in name:
        return "body"
    elif "metacarpals_base2" in name or "base2" in name:
        return "metal"
    elif "metacarpals" in name:
        return "joint"
    elif "distal" in name:
        return "body"
    elif "proximal" in name:
        return "joint"
    elif "grip" in name or "pad" in name:
        return "grip"
    else:
        return "body"


def get_material_settings(part_type, scheme_name):
    if scheme_name == "none" or scheme_name not in COLOR_SCHEMES:
        return None, 0.5, 0.0
    colors = COLOR_SCHEMES[scheme_name]
    color = colors.get(part_type, colors["body"])
    if part_type == "body":
        return color, 0.35, 0.15
    elif part_type == "joint":
        return color, 0.45, 0.65
    elif part_type == "grip":
        return color, 0.85, 0.05
    else:
        return color, 0.25, 0.85


def create_material(obj, part_type, scheme_name):
    color, roughness, metallic = get_material_settings(part_type, scheme_name)
    if color is None:
        return
    mat_name = f"Mat_{scheme_name}_{part_type}_{obj.name}"
    mat = bpy.data.materials.new(name=mat_name)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
    obj.data.materials.append(mat)


def rpy_to_matrix(r, p, y):
    """Convert URDF roll-pitch-yaw to 4x4 rotation matrix (Rz @ Ry @ Rx)."""
    rx = Matrix.Rotation(r, 4, 'X')
    ry = Matrix.Rotation(p, 4, 'Y')
    rz = Matrix.Rotation(y, 4, 'Z')
    return rz @ ry @ rx


def parse_urdf(urdf_path):
    """Parse URDF, compute world transforms for each link's visual mesh.
    Returns list of (link_name, mesh_abs_path, world_matrix_4x4).
    """
    tree = ET.parse(urdf_path)
    root = tree.getroot()
    urdf_dir = os.path.dirname(urdf_path)

    # Collect links: name -> {mesh, xyz, rpy}
    links = {}
    for link_elem in root.findall('link'):
        name = link_elem.get('name')
        visual = link_elem.find('visual')
        if visual is None:
            continue
        mesh_elem = visual.find('geometry/mesh')
        if mesh_elem is None:
            continue
        mesh_file = mesh_elem.get('filename')
        xyz = [0.0, 0.0, 0.0]
        rpy = [0.0, 0.0, 0.0]
        origin = visual.find('origin')
        if origin is not None:
            xyz_str = origin.get('xyz', '0 0 0')
            rpy_str = origin.get('rpy', '0 0 0')
            xyz = [float(x) for x in xyz_str.split()]
            rpy = [float(x) for x in rpy_str.split()]
        links[name] = {'mesh': mesh_file, 'xyz': xyz, 'rpy': rpy}

    # Collect joints: parent -> child with origin transform
    joints = []
    for joint_elem in root.findall('joint'):
        parent = joint_elem.find('parent').get('link')
        child = joint_elem.find('child').get('link')
        xyz = [0.0, 0.0, 0.0]
        rpy = [0.0, 0.0, 0.0]
        origin = joint_elem.find('origin')
        if origin is not None:
            xyz_str = origin.get('xyz', '0 0 0')
            rpy_str = origin.get('rpy', '0 0 0')
            xyz = [float(x) for x in xyz_str.split()]
            rpy = [float(x) for x in rpy_str.split()]
        joints.append({'parent': parent, 'child': child, 'xyz': xyz, 'rpy': rpy})

    # Build child map: parent_link -> [joint, ...]
    child_map = {}
    for j in joints:
        child_map.setdefault(j['parent'], []).append(j)

    # Find root links (appear as parent but never as child)
    all_children = set(j['child'] for j in joints)
    all_parents = set(j['parent'] for j in joints)
    root_links = all_parents - all_children
    if not root_links:
        root_links = set(links.keys())

    # BFS to compute world transforms
    world_transforms = {}
    for rl in root_links:
        world_transforms[rl] = Matrix.Identity(4)
        queue = [rl]
        while queue:
            current = queue.pop(0)
            for j in child_map.get(current, []):
                child = j['child']
                rot = rpy_to_matrix(j['rpy'][0], j['rpy'][1], j['rpy'][2])
                trans = Matrix.Translation(Vector(j['xyz']))
                joint_tf = world_transforms[current] @ trans @ rot
                if child in links:
                    vrot = rpy_to_matrix(links[child]['rpy'][0], links[child]['rpy'][1], links[child]['rpy'][2])
                    vtrans = Matrix.Translation(Vector(links[child]['xyz']))
                    world_transforms[child] = joint_tf @ vtrans @ vrot
                else:
                    world_transforms[child] = joint_tf
                queue.append(child)

    # Resolve mesh absolute paths
    result = []
    for link_name, info in links.items():
        mesh_rel = info['mesh']
        mesh_abs = os.path.join(urdf_dir, mesh_rel)
        if not os.path.exists(mesh_abs):
            base = os.path.basename(mesh_rel)
            meshes_dir = os.path.join(urdf_dir, 'meshes')
            if os.path.isdir(meshes_dir):
                for f in os.listdir(meshes_dir):
                    if f.lower() == base.lower():
                        mesh_abs = os.path.join(meshes_dir, f)
                        break
        world_mat = world_transforms.get(link_name, Matrix.Identity(4))
        result.append((link_name, mesh_abs, world_mat))

    return result


def scan_stl_files(input_dir, recursive):
    stl_files = []
    if recursive:
        for root, dirs, files in os.walk(input_dir):
            for f in files:
                if f.lower().endswith('.stl'):
                    stl_files.append(os.path.join(root, f))
    else:
        for f in os.listdir(input_dir):
            if f.lower().endswith('.stl'):
                stl_files.append(os.path.join(input_dir, f))
    return sorted(stl_files)


def clear_scene():
    """Remove all objects, meshes, and materials from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)


# ========== Operators ==========

class STL_OT_select_input(bpy.types.Operator):
    bl_idname = "stl_transformer.select_input"
    bl_label = "Select Input Directory"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        context.scene.stl_input_dir = self.directory
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


class STL_OT_select_output(bpy.types.Operator):
    bl_idname = "stl_transformer.select_output"
    bl_label = "Select Output Directory"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        context.scene.stl_output_dir = self.directory
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


class STL_OT_select_urdf(bpy.types.Operator):
    bl_idname = "stl_transformer.select_urdf"
    bl_label = "Select URDF File"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        context.scene.stl_urdf_path = self.filepath
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}


class STL_OT_convert(bpy.types.Operator):
    bl_idname = "stl_transformer.convert"
    bl_label = "Convert"
    bl_description = "Batch convert STL to GLB and OBJ"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        mode = scene.stl_mode
        output_dir = scene.stl_output_dir
        color_scheme = scene.stl_color_scheme
        export_glb = scene.stl_export_glb
        export_obj = scene.stl_export_obj

        if not output_dir:
            self.report({'ERROR'}, "Please set output directory")
            return {'CANCELLED'}
        if not export_glb and not export_obj:
            self.report({'ERROR'}, "Select at least one export format")
            return {'CANCELLED'}

        os.makedirs(output_dir, exist_ok=True)

        if mode == 'URDF':
            return self.assemble_urdf(context, scene, output_dir, color_scheme, export_glb, export_obj)
        else:
            return self.convert_individual(context, scene, output_dir, color_scheme, export_glb, export_obj)

    def convert_individual(self, context, scene, output_dir, color_scheme, export_glb, export_obj):
        input_dir = scene.stl_input_dir
        recursive = scene.stl_recursive
        overwrite = scene.stl_overwrite

        if not input_dir or not os.path.isdir(input_dir):
            self.report({'ERROR'}, "Input directory does not exist")
            return {'CANCELLED'}

        stl_files = scan_stl_files(input_dir, recursive)
        if not stl_files:
            self.report({'WARNING'}, "No STL files found")
            return {'CANCELLED'}

        success_count = 0
        fail_count = 0

        for i, stl_path in enumerate(stl_files):
            stl_name = os.path.basename(stl_path)
            base_name = os.path.splitext(stl_name)[0]
            rel_path = os.path.relpath(stl_path, input_dir)
            rel_dir = os.path.dirname(rel_path)
            out_subdir = os.path.join(output_dir, rel_dir)
            os.makedirs(out_subdir, exist_ok=True)
            glb_path = os.path.join(out_subdir, base_name + ".glb")
            obj_path = os.path.join(out_subdir, base_name + ".obj")

            if not overwrite and (os.path.exists(glb_path) or os.path.exists(obj_path)):
                continue

            try:
                clear_scene()
                bpy.ops.wm.stl_import(filepath=stl_path)
                obj = bpy.context.active_object
                if obj is None and bpy.context.selected_objects:
                    obj = bpy.context.selected_objects[0]
                if obj is None:
                    fail_count += 1
                    continue
                obj.name = base_name
                part_type = get_part_type(stl_name)
                create_material(obj, part_type, color_scheme)

                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                if export_glb:
                    bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=True)
                if export_obj:
                    bpy.ops.wm.obj_export(filepath=obj_path, export_selected_objects=True)
                success_count += 1
            except Exception as e:
                fail_count += 1
                print(f"FAIL: {stl_name} -> {e}")

        clear_scene()
        msg = f"Done! Success {success_count}/{len(stl_files)}"
        if fail_count > 0:
            msg += f", Failed {fail_count}"
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def assemble_urdf(self, context, scene, output_dir, color_scheme, export_glb, export_obj):
        urdf_path = scene.stl_urdf_path
        join_meshes = scene.stl_join_meshes

        if not urdf_path or not os.path.isfile(urdf_path):
            self.report({'ERROR'}, "URDF file does not exist")
            return {'CANCELLED'}

        try:
            link_list = parse_urdf(urdf_path)
        except Exception as e:
            self.report({'ERROR'}, f"URDF parse failed: {e}")
            return {'CANCELLED'}

        if not link_list:
            self.report({'WARNING'}, "No meshes found in URDF")
            return {'CANCELLED'}

        clear_scene()

        imported = []
        for link_name, mesh_path, world_mat in link_list:
            if not os.path.exists(mesh_path):
                print(f"SKIP (file not found): {link_name} -> {mesh_path}")
                continue
            try:
                bpy.ops.wm.stl_import(filepath=mesh_path)
                obj = bpy.context.active_object
                if obj is None and bpy.context.selected_objects:
                    obj = bpy.context.selected_objects[0]
                if obj is None:
                    continue
                obj.name = link_name
                obj.matrix_world = world_mat.copy()
                part_type = get_part_type(os.path.basename(mesh_path))
                create_material(obj, part_type, color_scheme)
                imported.append(obj)
            except Exception as e:
                print(f"FAIL import {link_name}: {e}")

        if not imported:
            self.report({'ERROR'}, "No meshes could be imported")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        for obj in imported:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = imported[0]

        urdf_name = os.path.splitext(os.path.basename(urdf_path))[0]
        glb_path = os.path.join(output_dir, urdf_name + "_assembled.glb")
        obj_path = os.path.join(output_dir, urdf_name + "_assembled.obj")

        try:
            if export_glb:
                bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=True)
            if export_obj:
                if join_meshes:
                    bpy.context.view_layer.objects.active = imported[0]
                    bpy.ops.object.join()
                    obj_joined = bpy.context.active_object
                    obj_joined.select_set(True)
                    bpy.ops.wm.obj_export(filepath=obj_path, export_selected_objects=True)
                else:
                    bpy.ops.wm.obj_export(filepath=obj_path, export_selected_objects=True)
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}

        clear_scene()
        self.report({'INFO'}, f"Assembled {len(imported)} parts -> {urdf_name}_assembled")
        return {'FINISHED'}


# ========== Panel ==========

class STL_PT_main_panel(bpy.types.Panel):
    bl_label = "STL Transformer"
    bl_idname = "STL_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "STL Transformer"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        try:
            box = layout.box()
            box.label(text="Mode")
            box.prop(scene, "stl_mode", text="")

            if scene.stl_mode == 'INDIVIDUAL':
                box = layout.box()
                box.label(text="Input Settings")
                row = box.row(align=True)
                row.prop(scene, "stl_input_dir", text="")
                row.operator("stl_transformer.select_input", text="Browse")
                box.prop(scene, "stl_recursive")
            else:
                box = layout.box()
                box.label(text="URDF File")
                row = box.row(align=True)
                row.prop(scene, "stl_urdf_path", text="")
                row.operator("stl_transformer.select_urdf", text="Browse")

            box = layout.box()
            box.label(text="Output Settings")
            row = box.row(align=True)
            row.prop(scene, "stl_output_dir", text="")
            row.operator("stl_transformer.select_output", text="Browse")
            if scene.stl_mode == 'INDIVIDUAL':
                box.prop(scene, "stl_overwrite")

            box = layout.box()
            box.label(text="Export Format")
            row = box.row()
            row.prop(scene, "stl_export_glb")
            row.prop(scene, "stl_export_obj")

            if scene.stl_mode == 'URDF':
                box = layout.box()
                box.label(text="Assembly Options")
                box.prop(scene, "stl_join_meshes")

            box = layout.box()
            box.label(text="Color Scheme")
            box.prop(scene, "stl_color_scheme", text="")

            layout.separator()
            col = layout.column()
            col.scale_y = 1.8
            if scene.stl_mode == 'INDIVIDUAL':
                col.operator("stl_transformer.convert", text="Start Conversion")
            else:
                col.operator("stl_transformer.convert", text="Assemble & Export")

        except Exception as e:
            layout.label(text="ERROR in draw():")
            layout.label(text=str(e))
            layout.label(text=traceback.format_exc()[:200])


# ========== Register ==========

classes = (
    STL_OT_select_input,
    STL_OT_select_output,
    STL_OT_select_urdf,
    STL_OT_convert,
    STL_PT_main_panel,
)


def register():
    old_props = [
        "stl_converter_props",
        "stl_input_dir",
        "stl_output_dir",
        "stl_color_scheme",
        "stl_export_glb",
        "stl_export_obj",
        "stl_recursive",
        "stl_overwrite",
        "stl_mode",
        "stl_urdf_path",
        "stl_join_meshes",
    ]
    for prop_name in old_props:
        if hasattr(bpy.types.Scene, prop_name):
            try:
                delattr(bpy.types.Scene, prop_name)
            except:
                pass

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.stl_mode = bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('INDIVIDUAL', "Individual Files", "Batch convert each STL separately"),
            ('URDF', "URDF Assembly", "Assemble parts using URDF transforms into complete model"),
        ],
        default='INDIVIDUAL',
    )
    bpy.types.Scene.stl_input_dir = bpy.props.StringProperty(
        name="Input Dir",
        description="Folder containing STL files",
        default="",
        subtype='DIR_PATH',
    )
    bpy.types.Scene.stl_output_dir = bpy.props.StringProperty(
        name="Output Dir",
        description="Output folder",
        default="",
        subtype='DIR_PATH',
    )
    bpy.types.Scene.stl_urdf_path = bpy.props.StringProperty(
        name="URDF Path",
        description="Path to URDF file",
        default="",
        subtype='FILE_PATH',
    )
    bpy.types.Scene.stl_color_scheme = bpy.props.EnumProperty(
        name="Color",
        items=[
            ('none', "None", "No material"),
            ('light_blue', "Light Blue", "Light blue body + dark joints"),
            ('white', "White", "White body + dark joints"),
            ('beige', "Beige", "Warm beige body + dark joints"),
            ('robotic', "Robotic Gray", "Dark metallic style"),
        ],
        default='light_blue',
    )
    bpy.types.Scene.stl_export_glb = bpy.props.BoolProperty(
        name="GLB",
        default=True,
    )
    bpy.types.Scene.stl_export_obj = bpy.props.BoolProperty(
        name="OBJ",
        default=True,
    )
    bpy.types.Scene.stl_recursive = bpy.props.BoolProperty(
        name="Recursive",
        default=True,
    )
    bpy.types.Scene.stl_overwrite = bpy.props.BoolProperty(
        name="Overwrite",
        default=True,
    )
    bpy.types.Scene.stl_join_meshes = bpy.props.BoolProperty(
        name="Join Meshes",
        description="Merge all parts into a single mesh object for OBJ export",
        default=False,
    )

    print("[STL Transformer] v2.0 Registered OK!")


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass

    for prop_name in ["stl_input_dir", "stl_output_dir", "stl_color_scheme",
                       "stl_export_glb", "stl_export_obj", "stl_recursive",
                       "stl_overwrite", "stl_mode", "stl_urdf_path",
                       "stl_join_meshes", "stl_converter_props"]:
        if hasattr(bpy.types.Scene, prop_name):
            try:
                delattr(bpy.types.Scene, prop_name)
            except:
                pass


if __name__ == "__main__":
    register()
