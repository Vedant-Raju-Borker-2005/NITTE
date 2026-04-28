import numpy as np
from pathlib import Path

def create_better_test_image(filename='data/test_with_plumes.npy', num_plumes=3):
    """Create hyperspectral image with realistic methane plumes"""
    
    # Create base image: 11 bands, 512x512 pixels
    image = np.random.randn(11, 512, 512) * 0.05 + 0.5
    image = np.clip(image, 0, 1)
    
    # Define plume locations
    plume_locs = [(150, 150), (300, 350), (400, 200)][:num_plumes]
    
    for plume_idx, (cy, cx) in enumerate(plume_locs):
        # Create Gaussian plume
        yy, xx = np.ogrid[:512, :512]
        radius = 60 + plume_idx * 10
        gaussian = np.exp(-((xx-cx)**2 + (yy-cy)**2) / (radius**2))
        
        # Methane has strongest absorption at Band 0 (1.6 μm)
        image[0] -= gaussian * 0.7  # Strong CH4 absorption
        
        # Secondary absorption at Band 10 (2.3 μm)
        image[10] -= gaussian * 0.4
        
        # Weak absorption in other SWIR bands (8, 9)
        image[8] -= gaussian * 0.3
        image[9] -= gaussian * 0.25
        
        print(f"✅ Plume {plume_idx+1}: ({cy}, {cx})")
    
    # Ensure valid range
    image = np.clip(image, 0, 1)
    
    # Save
    Path('data').mkdir(exist_ok=True)
    np.save(filename, image)
    print(f"\n✅ Saved: {filename}")
    print(f"   Shape: {image.shape}")
    print(f"   Range: [{image.min():.3f}, {image.max():.3f}]")
    
    return image

# Create and test
if __name__ == '__main__':
    create_better_test_image()
