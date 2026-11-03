/*
 * platina_trampoline.S — A55 startup trampoline for the PLATINA handoff.
 *
 * PSCI CPU_ON enters the target at the highest implemented non-secure EL
 * (EL2 on this v8.0 SoC), but the XNU iOS kernel must run at EL1. This
 * trampoline detects the current EL, drops EL2->EL1 (clearing the usual
 * EL2 traps: HCR, CPTR, HSTR, CNTHCTL, CNTVOFF, ICC_SRE_EL2), and jumps
 * into XNU with x0 = boot_args.
 *
 * The shim patches the two .quad literals at TRAMP_LITERALS_OFF with
 * (boot_args_pa, entry_pa) and starts the A55 at platina_trampoline_start.
 * Position-independent: PC-relative literals only.
 */
.section .text.platina_trampoline, "ax"
.align 6
.globl platina_trampoline_start
.globl platina_trampoline_end
.type platina_trampoline_start, %function
platina_trampoline_start:
	/* marker 1: core arrived at the trampoline (green 5 lines at lit_paint) */
	ldr	x4, lit_paint
	ldr	w5, lit_color
	mov	w6, #5400		/* 5 lines * 1080 */
1:	str	w5, [x4], #4
	subs	w6, w6, #1
	b.ne	1b
	dsb	sy

	mrs	x3, CurrentEL		/* 0x4=EL1, 0x8=EL2 */
	cmp	x3, #0x8
	b.eq	2f

	/* entered at EL1: second marker (inverted, one line down) then straight in */
	mov	x6, #43200		/* +10 lines */
	add	x4, x4, x6
	ldr	w5, lit_color
	eor	w5, w5, #0x00ffffff	/* inverted: white-ish */
	mov	w6, #5400
3:	str	w5, [x4], #4
	subs	w6, w6, #1
	b.ne	3b
	dsb	sy

	ldr	x0, lit_ba
	ldr	x1, lit_entry
	br	x1

2:	/* entered at EL2: drop to EL1. Minimal: SPSR/ELR/ERET only - every
	 * other EL2 register keeps its warm-boot reset value (HCR=0: no
	 * stage-2; CPTR=0: no FP traps; the kernel sets the rest itself at
	 * EL1, and anything we write here may trap to EL3 on this firmware). */
	ldr	x0, lit_ba		/* x0 = boot_args for XNU */
	ldr	x1, lit_entry		/* x1 = kernel entry */
	mov	x2, #0x3c5		/* SPSR_EL2: DAIF masked, EL1h */
	msr	spsr_el2, x2
	msr	elr_el2, x1

	/* marker 2: drop completed (inverted color, one line down) */
	mov	x6, #43200		/* +10 lines */
	add	x4, x4, x6
	ldr	w5, lit_color
	eor	w5, w5, #0x00ffffff
	mov	w6, #5400
4:	str	w5, [x4], #4
	subs	w6, w6, #1
	b.ne	4b
	dsb	sy

	eret

.align 3
lit_ba:		.quad	0		/* shim patches: boot_args physical address */
lit_entry:	.quad	0		/* shim patches: kernel entry physical address */
lit_paint:	.quad	0		/* shim patches: framebuffer marker address */
lit_color:	.word	0xff00ff00	/* marker color */
		.word	0
platina_trampoline_end:
.size platina_trampoline_start, platina_trampoline_end - platina_trampoline_start
