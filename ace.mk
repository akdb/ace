
ACE_SOURCES=$(wildcard */*.aces)

define acehandler

-include $(subst .acec,.d,$1)
.PHONY: $(subst .acec,.d,$1)

$(1): $(2)
	python ace/ace.py -l -o $(1) $(2)

$(1:.acec=.o): $(1) $(2)
	$(CC) $(CFLAGS) -I$(dir $(2)) -c -x c -o $(1:.acec=.o) $(1)
	$(CC) $(CFLAGS) -I$(dir $(2)) -c -x c -MF $(1:.acec=.d) -MT $(1:.acec=.o) -MM $(1)
endef

$(foreach src,$(ACE_SOURCES),$(eval $(call acehandler,$(addprefix ../build/,$(subst .aces,.acec,$(notdir $(src)))),$(src))))

