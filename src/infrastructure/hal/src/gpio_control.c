/*
 * GPIO Control for LEDs and Buttons
 */

#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>

#define LED_STATUS_GPIO 216
#define LED_RECORDING_GPIO 217
#define BUTTON_GPIO 218

int gpio_export(int gpio) {
    int fd = open("/sys/class/gpio/export", O_WRONLY);
    if (fd < 0) return -1;
    dprintf(fd, "%d", gpio);
    close(fd);
    return 0;
}

int gpio_set_direction(int gpio, const char *dir) {
    char path[64];
    snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/direction", gpio);
    int fd = open(path, O_WRONLY);
    if (fd < 0) return -1;
    write(fd, dir, strlen(dir));
    close(fd);
    return 0;
}

int gpio_write(int gpio, int value) {
    char path[64];
    snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/value", gpio);
    int fd = open(path, O_WRONLY);
    if (fd < 0) return -1;
    dprintf(fd, "%d", value);
    close(fd);
    return 0;
}

void led_status(int on) {
    gpio_write(LED_STATUS_GPIO, on);
}

void led_recording(int on) {
    gpio_write(LED_RECORDING_GPIO, on);
}