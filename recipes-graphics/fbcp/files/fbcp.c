#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/fb.h>
#include <signal.h>

static volatile int running = 1;

void sighandler(int sig) {
    running = 0;
}

int main() {
    int fb0, fb2;
    struct fb_var_screeninfo vinfo0, vinfo2;
    struct fb_fix_screeninfo finfo0, finfo2;
    unsigned char *fb0_map, *fb2_map;
    long fb0_size, fb2_size;
    
    signal(SIGINT, sighandler);
    signal(SIGTERM, sighandler);
    
    fb0 = open("/dev/fb0", O_RDONLY);
    fb2 = open("/dev/fb2", O_WRONLY);
    
    if (fb0 < 0 || fb2 < 0) {
        perror("Error opening framebuffers");
        return 1;
    }
    
    ioctl(fb0, FBIOGET_VSCREENINFO, &vinfo0);
    ioctl(fb0, FBIOGET_FSCREENINFO, &finfo0);
    ioctl(fb2, FBIOGET_VSCREENINFO, &vinfo2);
    ioctl(fb2, FBIOGET_FSCREENINFO, &finfo2);
    
    fb0_size = vinfo0.yres_virtual * finfo0.line_length;
    fb2_size = vinfo2.yres_virtual * finfo2.line_length;
    
    fb0_map = mmap(NULL, fb0_size, PROT_READ, MAP_SHARED, fb0, 0);
    fb2_map = mmap(NULL, fb2_size, PROT_WRITE, MAP_SHARED, fb2, 0);
    
    if (fb0_map == MAP_FAILED || fb2_map == MAP_FAILED) {
        perror("mmap failed");
        return 1;
    }
    
    printf("fbcp: HDMI(%dx%d %dbpp) -> LCD(%dx%d %dbpp)\n",
           vinfo0.xres, vinfo0.yres, vinfo0.bits_per_pixel,
           vinfo2.xres, vinfo2.yres, vinfo2.bits_per_pixel);
    
    // Main copy loop with RGB32->RGB565 conversion
    int pixels = vinfo2.xres * vinfo2.yres;
    
    while (running) {
        unsigned char *src = fb0_map;
        unsigned short *dst = (unsigned short *)fb2_map;
        
        // Convert RGB32 (BGRA) to RGB565
        for (int i = 0; i < pixels; i++) {
            unsigned char b = *src++;
            unsigned char g = *src++;
            unsigned char r = *src++;
            src++; // skip alpha
            
            // Convert to RGB565: RRRRRGGGGGGBBBBB
            *dst++ = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
        }
        
        usleep(100000); // 10 FPS - low CPU usage
    }
    
    munmap(fb0_map, fb0_size);
    munmap(fb2_map, fb2_size);
    close(fb0);
    close(fb2);
    
    printf("fbcp stopped\n");
    return 0;
}
