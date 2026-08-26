"""Render the ROBONEXUS robot from its own URDF and CAD meshes.

A small software rasteriser: forward-kinematics the URDF at zero joint angles,
load every visual mesh, project orthographically and z-buffer it with flat
shading. Orthographic + flat shading is the point — it produces a technical
drawing rather than a game screenshot, which is the register the site uses.

No 3D libraries: numpy and Pillow only.
"""
import os, struct, math
import numpy as np
import xml.etree.ElementTree as ET
from PIL import Image

URDF  = '//wsl.localhost/Ubuntu-20.04/home/user/robot2_render.urdf'
PKG   = '//wsl.localhost/Ubuntu-20.04/home/user/catkin_ws/src/Robot2_description'
OUT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'robot')

# ---------- maths ----------
def rpy_to_R(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    Rx = np.array([[1,0,0],[0,cr,-sr],[0,sr,cr]])
    Ry = np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]])
    Rz = np.array([[cy,-sy,0],[sy,cy,0],[0,0,1]])
    return Rz @ Ry @ Rx           # URDF rpy is fixed-axis XYZ

def T(xyz, rpy):
    M = np.eye(4); M[:3,:3] = rpy_to_R(*rpy); M[:3,3] = xyz; return M

def parse_origin(el):
    o = el.find('origin') if el is not None else None
    if o is None: return T([0,0,0],[0,0,0])
    xyz = [float(v) for v in o.get('xyz','0 0 0').split()]
    rpy = [float(v) for v in o.get('rpy','0 0 0').split()]
    return T(xyz, rpy)

# ---------- meshes ----------
def load_stl(path):
    with open(path,'rb') as f: data = f.read()
    if data[:5].lower() == b'solid' and b'facet' in data[:2000]:
        verts=[]
        for line in data.decode('utf-8','ignore').splitlines():
            s=line.strip()
            if s.startswith('vertex'):
                verts.append([float(x) for x in s.split()[1:4]])
        v=np.array(verts,dtype=np.float64)
        return v.reshape(-1,3,3)
    n = struct.unpack('<I', data[80:84])[0]
    tri = np.zeros((n,3,3))
    off = 84
    for i in range(n):
        vals = struct.unpack('<12f', data[off:off+48])
        tri[i,0]=vals[3:6]; tri[i,1]=vals[6:9]; tri[i,2]=vals[9:12]
        off += 50
    return tri

def mesh_path(fn):
    fn = fn.replace('package://robot2_description/','')
    return PKG + '/' + fn

def box_tris(sx,sy,sz):
    x,y,z = sx/2, sy/2, sz/2
    v=np.array([[-x,-y,-z],[x,-y,-z],[x,y,-z],[-x,y,-z],
                [-x,-y, z],[x,-y, z],[x,y, z],[-x,y, z]])
    f=[(0,1,2),(0,2,3),(4,6,5),(4,7,6),(0,4,5),(0,5,1),
       (1,5,6),(1,6,2),(2,6,7),(2,7,3),(3,7,4),(3,4,0)]
    return np.array([[v[a],v[b],v[c]] for a,b,c in f])

def cyl_tris(r,l,seg=24):
    a=np.linspace(0,2*math.pi,seg,endpoint=False)
    top=np.stack([r*np.cos(a),r*np.sin(a),np.full(seg,l/2)],1)
    bot=np.stack([r*np.cos(a),r*np.sin(a),np.full(seg,-l/2)],1)
    tris=[]
    for i in range(seg):
        j=(i+1)%seg
        tris += [[bot[i],bot[j],top[j]],[bot[i],top[j],top[i]],
                 [[0,0,l/2],top[i],top[j]],[[0,0,-l/2],bot[j],bot[i]]]
    return np.array(tris,dtype=np.float64)

# ---------- URDF ----------
root = ET.parse(URDF).getroot()
links, joints = {}, []
for l in root.findall('link'):
    vis=[]
    for v in l.findall('visual'):
        g=v.find('geometry'); 
        if g is None: continue
        M=parse_origin(v)
        col=None
        mat=v.find('material')
        if mat is not None:
            c=mat.find('color')
            if c is not None:
                col=[float(x) for x in c.get('rgba','.7 .7 .7 1').split()][:3]
        m=g.find('mesh'); b=g.find('box'); cy=g.find('cylinder'); sp=g.find('sphere')
        if m is not None:
            sc=[float(x) for x in m.get('scale','1 1 1').split()]
            vis.append(('mesh', mesh_path(m.get('filename')), sc, M, col))
        elif b is not None:
            vis.append(('box', [float(x) for x in b.get('size').split()], None, M, col))
        elif cy is not None:
            vis.append(('cyl', [float(cy.get('radius')), float(cy.get('length'))], None, M, col))
    links[l.get('name')] = vis
for j in root.findall('joint'):
    p=j.find('parent'); c=j.find('child')
    if p is None or c is None: continue
    joints.append((p.get('link'), c.get('link'), parse_origin(j)))

children={}
for p,c,M in joints: children.setdefault(p,[]).append((c,M))
allc={c for _,c,_ in joints}
roots=[n for n in links if n not in allc]
world={}
def walk(n, M):
    world[n]=M
    for c,J in children.get(n,[]): walk(c, M @ J)
for r in roots: walk(r, np.eye(4))

# ---------- gather triangles ----------
tris=[]; cols=[]
for name, vis in links.items():
    if name not in world: continue
    W = world[name]
    for kind, a, sc, M, col in vis:
        try:
            if kind=='mesh':
                t = load_stl(a)
                if sc: t = t * np.array(sc)
            elif kind=='box': t = box_tris(*a)
            else: t = cyl_tris(*a)
        except Exception as e:
            print('  skip', name, e); continue
        F = W @ M
        pts = t.reshape(-1,3)
        pts = (F[:3,:3] @ pts.T).T + F[:3,3]
        tris.append(pts.reshape(-1,3,3))
        cols.append(np.tile(np.array(col if col else [.66,.67,.64]), (len(t),1)))
tris=np.concatenate(tris); cols=np.concatenate(cols)
print('triangles:', len(tris))
lo, hi = tris.reshape(-1,3).min(0), tris.reshape(-1,3).max(0)
print('bbox  min %s\n      max %s\n      size %s' % (np.round(lo,4), np.round(hi,4), np.round(hi-lo,4)))
np.save(os.path.join(OUT,'tris.npy'), tris); np.save(os.path.join(OUT,'cols.npy'), cols)
