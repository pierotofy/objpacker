import os
import rasterio
#from rasterio.io import MemoryFile
import warnings
import numpy as np
from imagepacker.utils import AABB
from imagepacker import pack

warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

def load_obj(obj_path, _info=print):
    if not os.path.isfile(obj_path):
        raise IOError("Cannot open %s" % obj_path)

    obj_base_path = os.path.dirname(os.path.abspath(obj_path))
    obj = {
        'filename': os.path.basename(obj_path),
        'root_dir': os.path.dirname(os.path.abspath(obj_path)),
        'mtl_filenames': [],
        'materials': {},
    }
    vertices = []
    uvs = []
    normals = []

    faces = {}
    current_material = "_"

    with open(obj_path) as f:
        _info("Loading %s" % obj_path)

        for line in f:
            if line.startswith("mtllib "):
                # Materials
                mtl_file = "".join(line.split()[1:]).strip()
                obj['materials'].update(load_mtl(mtl_file, obj_base_path, _info=_info))
                obj['mtl_filenames'].append(mtl_file)
            elif line.startswith("v "):
                # Vertices
                vertices.append(list(map(float, line.split()[1:4])))
            elif line.startswith("vt "):
                # UVs
                uvs.append(list(map(float, line.split()[1:3])))
            elif line.startswith("vn "):
                normals.append(list(map(float, line.split()[1:4])))
            elif line.startswith("usemtl "):
                mtl_name = "".join(line.split()[1:]).strip()
                if not mtl_name in obj['materials']:
                    raise Exception("%s material is missing" % mtl_name)

                current_material = mtl_name
            elif line.startswith("f "):
                if current_material not in faces:
                    faces[current_material] = []

                a,b,c = line.split()[1:]

                if a.count("/") == 2:
                    av, at, an = map(int, a.split("/")[0:3])
                    bv, bt, bn = map(int, b.split("/")[0:3])
                    cv, ct, cn = map(int, c.split("/")[0:3])

                    faces[current_material].append((av - 1, bv - 1, cv - 1, at - 1, bt - 1, ct - 1, an - 1, bn - 1, cn - 1)) 
                else:
                    av, at = map(int, a.split("/")[0:2])
                    bv, bt = map(int, b.split("/")[0:2])
                    cv, ct = map(int, c.split("/")[0:2])
                    faces[current_material].append((av - 1, bv - 1, cv - 1, at - 1, bt - 1, ct - 1)) 

    obj['vertices'] = np.array(vertices, dtype=np.float32)
    obj['uvs'] = np.array(uvs, dtype=np.float32)
    obj['normals'] = np.array(normals, dtype=np.float32)
    obj['faces'] = faces

    return obj

def load_mtl(mtl_file, obj_base_path, _info=print):
    mtl_file = os.path.join(obj_base_path, mtl_file)

    if not os.path.isfile(mtl_file):
        raise IOError("Cannot open %s" % mtl_file)

    mats = {}
    current_mtl = ""

    with open(mtl_file) as f:
        for line in f:
            if line.startswith("newmtl "):
                current_mtl = "".join(line.split()[1:]).strip()
            elif line.startswith("map_Kd ") and current_mtl:
                map_kd_filename = "".join(line.split()[1:]).strip()
                map_kd = os.path.join(obj_base_path, map_kd_filename)
                if not os.path.isfile(map_kd):
                    raise IOError("Cannot open %s" % map_kd)

                mats[current_mtl] = map_kd
    return mats


def write_obj_changes(obj_file, mtl_file, uv_changes, single_mat, output_dir):
    
    with open(obj_file) as f:
        obj_lines = f.readlines()
    
    out_lines = []
    uv_lines = []
    current_material = None

    printed_mtllib = False
    printed_usemtl = False

    for line_idx, line in enumerate(obj_lines):
        if line.startswith("mtllib"):
            if not printed_mtllib:
                out_lines.append("mtllib %s\n" % mtl_file)
                printed_mtllib = True
            else:
                out_lines.append("# \n")
        elif line.startswith("usemtl"):
            if not printed_usemtl:
                out_lines.append("usemtl %s\n" % single_mat)
                printed_usemtl = True
            else:
                out_lines.append("# \n")
            current_material = line[7:].strip()
        elif line.startswith("vt"):
            uv_lines.append(line_idx)
            out_lines.append(line)
        elif line.startswith("f"):
            for v in line[2:].split():
                parts = v.split("/")
                if len(parts) >= 2 and parts[1]:
                    uv_idx = int(parts[1]) - 1 # uv indexes start from 1
                    uv_line_idx = uv_lines[uv_idx]
                    uv_line = obj_lines[uv_line_idx][3:]
                    uv = [float(uv.strip()) for uv in uv_line.split()]

                    if current_material and current_material in uv_changes:
                        changes = uv_changes[current_material]
                        uv[0] = uv[0] * changes["aspect"][0] + changes["offset"][0]
                        uv[1] = uv[1] * changes["aspect"][1] + changes["offset"][1]
                        out_lines[uv_line_idx] = "vt %s %s\n" % (uv[0], uv[1])
            out_lines.append(line)
        else:
            out_lines.append(line)

    with open(os.path.join(output_dir, os.path.basename(obj_file)), 'w') as f:
        f.writelines(out_lines)

    # # Apply changes
    # for mat in uv_changes:
    #     changes = uv_changes[mat]
    #     faces = obj['faces'][mat]
    #     for f in faces:
    #         for uv_idx in f[3:6]:
    #             obj['uvs'][uv_idx][0] = obj['uvs'][uv_idx][0] * changes["aspect"][0] + changes["offset"][0]
    #             obj['uvs'][uv_idx][1] = obj['uvs'][uv_idx][1] * changes["aspect"][1] + changes["offset"][1]
                
    # with open(os.path.join(output_dir, obj['filename']), 'w') as f:
    #     f.write("mtllib %s\n" % mtl_file)
    #     for v in obj['vertices']:
    #         f.write("v %s %s %s\n" % (v[0], v[1], v[2]))
    #     for vt in obj['uvs']:
    #         f.write("vt %s %s\n" % (vt[0], vt[1]))
    #     for vn in obj['normals']:
    #         f.write("vn %s %s %s\n" % (vn[0], vn[1], vn[2]))
        
    #     f.write("usemtl %s\n" % single_mat)
    #     for mat in obj['faces']:
    #         print(mat)
    #         for face in obj['faces'][mat]:
    #             v = [i + 1 for i in face[0:3]]
    #             vt = [i + 1 for i in face[3:6]]
    #             vn = [i + 1 for i in face[6:9]]
    #             out = zip(v, vt) if not vn else zip(v, vt, vn)
    #             f.write("f %s\n" % " ".join(["/".join(map(str, t)) for t in out]))

def write_output_tex(img, profile, path):
    _, h, w = img.shape
    profile['width'] = w
    profile['height'] = h

    with rasterio.open(path, 'w', **profile) as dst:
        for b in range(1, img.shape[0] + 1):
            dst.write(img[b - 1], b)

    sidecar = path + '.aux.xml'
    if os.path.isfile(sidecar):
        os.unlink(sidecar)

def write_output_mtl(src_mtl, mat_file, dst_mtl):
    with open(src_mtl, 'r') as src:
        lines = src.readlines()

    out = []
    found_map = False
    single_mat = None

    for l in lines:
        if l.startswith("newmtl"):
            single_mat = "".join(l.split()[1:]).strip()
            out.append(l)
        elif l.startswith("map_Kd"):
            out.append("map_Kd %s\n" % mat_file)
            break
        else:
            out.append(l)
    
    with open(dst_mtl, 'w') as dst:
        dst.write("".join(out))

    if single_mat is None:
        raise Exception("Could not find material name in file")

    return single_mat

def obj_pack(obj_file, output_dir=None):
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(obj_file)), "packed")
    
    obj = load_obj(obj_file)
    if not obj['mtl_filenames']:
        raise Exception("No MTL files found, nothing to do")

    if os.path.abspath(obj_file) == os.path.abspath(os.path.join(output_dir, os.path.basename(obj_file))):
        raise Exception("This will overwrite %s. Choose a different output directory" % obj_file)
        
    # Compute AABB for UVs
    extents = {}
    for material in obj['materials']:
        bounds = AABB()

        faces = obj['faces'][material]
        for f in faces:
            for uv_idx in f[3:6]:
                uv = obj['uvs'][uv_idx]
                bounds.add(uv[0], uv[1])

        extents[material] = bounds
    
    output_image, uv_changes, profile = pack(obj, extents=extents)
    mtl_file = obj['mtl_filenames'][0]
    mat_file = os.path.basename(obj['materials'][next(iter(obj['materials']))])
    
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    write_output_tex(output_image, profile, os.path.join(output_dir, mat_file))
    single_mat = write_output_mtl(os.path.join(obj['root_dir'], mtl_file), mat_file, os.path.join(output_dir, mtl_file))
    write_obj_changes(obj_file, mtl_file, uv_changes, single_mat, output_dir)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Packs textured .OBJ Wavefront files into a single materials")
    parser.add_argument("obj", help="Path to the .OBJ file")
    parser.add_argument("-o","--output-dir", help="Output directory")
    args = parser.parse_args()

    obj_pack(args.obj, args.output_dir)