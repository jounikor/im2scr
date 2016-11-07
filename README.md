# im2scr
A simple python tool to convert any picture format supported by PIL.Image to ZX Spectrum or linear format.

The tool also supports cropping the original source picture to any size.

Note that this tool does not do extremely good job fixing errors in the source
picture. For example, if the picture has more than 2 colors in a 8x8 block,
the PAPER0 with no pixels has the highest priority. After that the color 
with most pixels gets selected. Therefore, use well "behaving" pictures as
source pictures.
