from flatparse.parsers.fixed_tail import FixedTailParser
from flatparse.parsers.fixed_width import FixedWidthParser

# Structure faithfully transcribed from the image:
#  - "Overall Sum" row: label only, NO index, NO name, then 4 values
#  - normal rows: bdry-part + index + name + 4 values
#  - rows 14/16: names so long the numbers shift right out of alignment
HEADER = "Surface-Part          Name              CM_x_v          CM_y_v          CM_z_v          Area[%]"
BLOCK = HEADER + "\n" + "\n".join([
    "        Overall Sum              5.017027756e-05   0.003367838416   -0.019856425184          100",
    "bdry-part   0    Fuselage_Front   1.034774793e-05  -0.000123201849   -0.001395066122   4.749649",
    "bdry-part   7    Fuselage_Cyl     1.404697376e-05   0.000186559411   -0.001197905875   22.769456",
    "bdry-part   8    Belly           -3.448091422e-05  -0.000002201812   -0.000642715768   9.127563",
    "bdry-part   9    MainWing_UpperSide   0.000253231463  -0.006354504448  -0.065065301345   13.814358",
    "bdry-part  14    IB_Engine_Core_Outlet_Duct   -2.003524753e-06   3.144768441e-05  -7.573246e-05   0.693187",
    "bdry-part  16    IB_Engine_Ventilation_Outlet_Duct   -2.099411240e-06   4.388504e-05  -0.000192821   0.596223",
])

print("="*70)
print("FixedWidthParser (expected to FAIL - columns shift with long names)")
print("="*70)
fw = FixedWidthParser().parse(BLOCK)
print("header:", fw.header)
print("n cols:", len(fw.header))
for r in fw.rows:
    print("  ", r)

print()
print("="*70)
print("FixedTailParser (anchors 4 value columns from the right)")
print("="*70)
ft = FixedTailParser(n_tail=4).parse(BLOCK)
print("header:", ft.header)
for r in ft.rows:
    print("  ", r)

print()
print("auto-detect n_tail:", FixedTailParser()._auto_n_tail(BLOCK.split("\n")[1:]))