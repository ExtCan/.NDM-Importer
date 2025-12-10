# Deep Dive: NDM Format Analysis and Detection

## Problem Statement
The NDM importer was breaking on all models after attempted fixes. This document details the deep analysis performed to understand the NDM format and create robust format detection.

## Investigation Process

### 1. Hex Data Analysis

#### KURIBO.NDM (Large Model - 4,221 vertices)
```
Node: kuribo
  Vertex count: 4,221
  Display list offset: 0x10220
  First command: 0x80 (QUAD), count=15,128
  
  Display list header: 32 bytes of GX setup commands before draw commands
  
  First 8 vertex references interpreted as different formats:
  
  3-byte format (pos:u8, attr:u8, uv:u8):
    pos indices: [0, 64, 0, 65, 0, 66, 0, 67]
    ✗ Alternating pattern, not sequential
    
  4-byte format (pos:u8, norm:u8, color:u8, uv:u8):
    pos indices: [0, 0, 0, 0, 0, 0, 0, 0]
    ✗ All zeros, no variety (false positive without variety check!)
    
  6-byte format (pos:u16, norm:u16, uv:u16):
    pos indices: [64, 65, 66, 67, 65, 64, 69, 70]
    ✓ Sequential, varied, valid
```

**Conclusion**: KURIBO requires 6-byte format (16-bit indices).

#### BIPLANE.NDM - engine node (456 vertices, but uses 3-byte!)
```
Node: engine
  Vertex count: 456 (> 255)
  First command: 0x80 (QUAD), count=64
  
  3-byte format:
    pos indices: [9, 13, 8, 14, 11, ...]
    ✓ Valid, varied, reasonable range
    
  6-byte format:
    pos indices: [2304, 2048, 2816, 3072, 3840, ...]
    ✗ Values exceed vertex count (456)
```

**Conclusion**: Having >255 vertices does NOT guarantee 6-byte format!

### 2. Pattern Recognition

#### Key Insights

1. **Variety is crucial**: All-zero or all-same indices indicate wrong format
   - KURIBO as 4-byte: [0,0,0,0,0,0,0,0] - rejected by variety check
   
2. **Validity check**: Indices must be < vertex_count
   - BIPLANE as 6-byte: [2304, 2048, ...] > 456 vertices - rejected
   
3. **Sequentiality with tolerance**: Real geometry has indices close together
   - ±3 was too strict (missed KURIBO: [64,65,66,67,65,64,69,70])
   - ±10 is better for strips and fans

4. **Draw command sizes**: Large models have HUGE draw commands
   - KURIBO: count=15,128 vertices in ONE command
   - Old MAX_DRAW_COUNT=2,000 was too small

### 3. Format Detection Algorithm

```python
For each potential format (3-byte, 4-byte, 6-byte):
  1. Sample first 8 vertex references
  2. Check validity: all(index < vertex_count)
  3. Check variety: len(set(indices)) > 1
  4. Check sequentiality: all(abs(diff) <= 10)
  
Priority:
  1. If 6-byte is valid + has variety + sequential → use 6-byte
  2. If 4-byte has pattern (bytes 1,2 both zero) → use 4-byte  
  3. If 3-byte or 4-byte is sequential → use respective format
  4. Check byte patterns (zeros in specific positions)
  5. Default to 3-byte
```

### 4. Comparison with Other GameCube Importers

Research into GameCube model formats revealed:
- **BMD/BDL format**: Uses similar display list structure
- **J3D format**: Also uses 8-bit or 16-bit indices
- **Key difference**: NDM uses 3/4/6-byte vertex refs, others use more complex attribute arrays

Common patterns:
- Display lists start with GX setup commands
- Draw commands: 0x80 (quads), 0x90 (triangles), 0x98 (strips), 0xA0 (fans)
- Vertex references can be 8-bit or 16-bit depending on vertex count

### 5. Test Results

| File | Vertices | Format | Faces | Status |
|------|----------|--------|-------|--------|
| KURIBO.NDM | 4,221 | 6-byte | 8,254 | ✓ |
| BIPLANE.NDM | 4,142 | 3-byte | 9,187 | ✓ |
| COIN.NDM | 496 | 3-byte | 960 | ✓ |
| ARROW.NDM | 151,962 | 3-byte | 300,920 | ✓ |
| STG_CAVE.NDM | 21,010 | 3-byte | 49,706 | ✓ |
| STG_ENTR.NDM | 34,877 | 3-byte | 77,438 | ✓ |
| ... | ... | ... | ... | ✓ |

**All 16 files parse successfully!**

## Technical Details

### Vertex Reference Formats

#### 3-byte format (most common):
```
Byte 0: Position index (u8)
Byte 1: Attribute/Normal index (u8, often 0)
Byte 2: UV index (u8)
```

#### 4-byte format (some stage files):
```
Byte 0: Position index (u8)
Byte 1: Normal index (u8, often 0)
Byte 2: Color index (u8, often 0)
Byte 3: UV index (u8)
```

#### 6-byte format (large models):
```
Bytes 0-1: Position index (u16 BE)
Bytes 2-3: Normal index (u16 BE)
Bytes 4-5: UV index (u16 BE)
```

### Constants Tuned

```python
MAX_DRAW_COUNT = 20000  # Was 2000, increased for KURIBO
MAX_SEQUENTIAL_DIFF = 10  # Was 3, relaxed for varied geometry
```

## Lessons Learned

1. **Never assume based on vertex count alone** - Format depends on actual indices used
2. **Variety checking is essential** - Prevents false positives from uniform data
3. **Be generous with limits** - GameCube games can have very large draw commands
4. **Test thoroughly** - Need to validate on all sample files, not just one or two

## References

- NDM format documentation (NDM_FORMAT_DOCUMENTATION.md)
- GameCube GX display list specification
- J3D/BMD format documentation (similar structure)
- Test results on all 16 sample NDM files
