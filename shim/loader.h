#pragma once
#include <stdint.h>

/* Boot the SWEETXNU payload found in the ABL ramdisk; returns only on error. */
const char *loader_boot(uintptr_t dtb);

/* Split path for the PLATINA A55 handoff: prepare copies the payload, places
 * the ADT and boot_args, and returns "" on success or the error string. The
 * caller then starts the kernel elsewhere (PSCI CPU_ON) with these. */
const char *loader_prepare(uintptr_t dtb);
uint64_t loader_entry_pa(void);      /* physical kernel entry */
uint64_t loader_bootargs_pa(void);   /* physical boot_args */
uint64_t loader_ramdisk_start(void); /* payload blob start (free after prepare) */
uint64_t loader_ramdisk_end(void);
