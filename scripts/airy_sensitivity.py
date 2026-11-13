from pathlib import Path
import tarfile
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'inputs'

with zipfile.ZipFile(INPUTS / 'crust-thick.zip') as f:
    lon, lat, published_thickness = np.loadtxt(f.open('crsthk.xyz')).T
with tarfile.open(INPUTS / 'crust1.0-addon.tar.gz') as f:
    kind = np.loadtxt(f.extractfile('CNtype1-1.txt'), dtype=str).ravel()
with tarfile.open(INPUTS / 'crust1.0.tar.gz') as f:
    bounds = np.loadtxt(f.extractfile('crust1.bnds'))
    density = np.loadtxt(f.extractfile('crust1.rho'))
continental = ~np.isin(kind, ('A0','A1','B-','V1','Y3','J-','K-','Y2'))
lat, bounds, density, published_thickness = (x[continental] for x in (lat,bounds,density,published_thickness))
area = 6371.0088**2*np.deg2rad(1)*(np.sin(np.deg2rad(lat+.5))-np.sin(np.deg2rad(lat-.5)))/1e6
layers = -np.diff(bounds,axis=1)
assert np.all(layers>=-1e-6)
rock_thickness = layers[:,2:].sum(axis=1)
rho_m, rho_w = 3.30, 1.03
k = 1-rho_w/rho_m
buoyancy = (layers[:,2:]*(1-density[:,2:8]/rho_m)).sum(axis=1)*1000
assert np.all((layers[:,2:]==0)|(density[:,2:8]>1))
# Remove modern water and ice loads in local Airy equilibrium.
dry_ref = (bounds[:,2]+(layers[:,:2]*density[:,:2]).sum(axis=1)/rho_m)*1000
# Preserve the model's wet fraction in the ice-unloaded reference at zero shift.
target = area[dry_ref<0].sum()
order = np.argsort(buoyancy)
offset = buoyancy[order][np.searchsorted(np.cumsum(area[order]),target)]
models = {'modern_relief': dry_ref,'airy_only':buoyancy-offset}
print('area',area.sum(),'rockvol',np.dot(area,rock_thickness)/1000,'published_vol',np.dot(area,published_thickness)/1000,'offset',offset,'ice',np.dot(area,layers[:,1])/1000)
for name,z in models.items():
    print(name,'relative shift, wet, 0-150, 0-200, 150-200')
    for s in (-200,-100,0,50,100,150,200,250,300,400,500):
        d=(s-z)/k
        print(s,*[round(area[m].sum(),3) for m in (d>0,(d>0)&(d<=150),(d>0)&(d<=200),(d>150)&(d<=200))])
    # Exact sliding interval maximum on the discretized grid, including shifts outside the displayed cases.
    order=np.argsort(z)
    x=z[order]
    a=np.r_[0,np.cumsum(area[order])]
    for d in (50,150,200):
        start=np.searchsorted(x,x-d*k,side='left')
        val=a[np.searchsorted(x,x,side='right')]-a[start]
        j=np.argmax(val)
        print('max width',d,round(val[j],3),'shift window upper edge',round(x[j],3))
    for exposed in [89.932,175.244,129.057,161.348]:
        ix=np.searchsorted(a,area.sum()-exposed)
        s=x[ix-1]+.00001
        d=(s-z)/k
        print('land target',exposed,'shift',round(s,2),'0-200',round(area[(d>0)&(d<=200)].sum(),2),'150-200',round(area[(d>150)&(d<=200)].sum(),2))
