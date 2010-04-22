#!/usr/bin/env python

# ACE - ASSS C Enricher - Generates full modules from pattern specifications for "a small subspace server"
# version beta 1
# Copyright (C) 2010 Justin M. Schwartz ("Arnk Kilo Dylie")

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/gpl-2.0.html>.

import sys, re
from cStringIO import StringIO
from optparse import OptionParser

class ProcessingException(Exception):
	def __init__(self, processor, value):
		self.processor = processor
		self.value = value
	def message(self):
		return self.processor.filename + ':' + str(self.processor.current_line) + ': error: ' + self.value
	def __str__(self):
		return repr(self.message())

class Processor:
	DirectiveEx = re.compile(r'^\$#(\w+)(.*)\s*?$')
	InlineEx = re.compile(r'^(\s*)\$(\w+)\((.*)\)[;]?(.*)\s*$')
	
	InterfaceUsageEx = re.compile(r'(\w+)->\w+?\(')
	StringEx = re.compile(r'\s*(".*")\s*')
	
	CPreprocessorEx = re.compile(r'^#(include|define) (\S+)[ ]?(.+)?\s*')

	NoParamEx = re.compile(r'^\s*$')
	
##directive: adviser

# Defines an adviser and begins an adviser block.
#End the block with $#endadviser
# Inside the block, functions should be specified in the order as they are
#listed in the adviser-type definition (see the relevant header file.)
# For functions that are not implemented, use $null() in place of a function.
# The adviser that is created will automatically be registered and unregistered
#in the module code.
# For more information on advisers, see
#http://bitbucket.org/grelminar/asss/wiki/Adviser

##param: scope: global or arena. with global, registers this adviser on load for
#all arenas. with arena, registers this adviser on attach to an arena.

##param: adviserIdOrType1: either the struct type (for example: Appk) or the adviser
#identifier (for example: A_PPK)
# this parameter expects typenames of the form Afoo or identifiers of the
#form A_FOO.
# if of neither form, this directive will assume that it is a typename

##[param]: adviserIdOrType2: if the struct type is specified for
#adviserIdOrType1, then this is the adviser identifier.
# if the adviser identifier is specified for adviserIdOrType1, then this is the
#struct type.
# if adviserIdOrType1 defaulted from not using the standard naming conventions,
#and adviserIdOrType2 is not provided, it will default to A_FOO, where FOO is
#the uppercase representation of the typename given in adviserIdOrType1

##
	AdviserParamEx = re.compile(r'^ (\w+) ([^ ]+)[ ]?([^ ]+)?$')
	def handleAdviser(processor, module, params):
		paramMatch = Processor.AdviserParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#adviser')

		scope = paramMatch.group(1)
		if scope <> 'global' and scope <> 'arena':
			raise ProcessingException(processor,
				'expected: "global" or "arena" as first parameter to $#adviser')

		advIdOrType1 = paramMatch.group(2)
		advId = None
		advType = None
		outOfConvention = False
		
		if advIdOrType1[0:2] == 'A_':
			advId = advIdOrType1
		elif advIdOrType1[0] == 'A':
			advType = advIdOrType1
		else:
			advType = advIdOrType1
			outOfConvention = True
			
		advIdOrType2 = paramMatch.group(3)
		if advIdOrType2:
			if advId:
				advType = advIdOrType2
			else:
				advId = advIdOrType2
		else:
			if outOfConvention:
				advId = 'A_' + advType.upper()
			elif advType:
				advId = 'A_' + advType[1:].upper()
			elif advId:
				advType = 'A' + advId[2:].lower()
				
		processor.active_adviser = module.createAdviser(scope, advType, advId)
		processor.active_adviser.file = processor.filename
		processor.active_adviser.line_number = processor.current_line

		return 'endadviser' # return the expected follow up directive
		

##directive: endadviser
# Closes an adviser block opened by $#adviser
##
	def handleEndadviser(processor, module, params):
		if not processor.active_adviser:
			raise ProcessingException(processor, 'unexpected $#endadviser')
					
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endadviser')
				
		processor.active_adviser = None
		return None


##directive: arenadata

# Defines the per-arena-data structure for the module; starts a structure block.
#End the block with $#endarenadata
# Inside the block, define structure fields normally.
# Only one arena data structure may be defined in a module, multiple arenadata
#directives just add extra members to the same struct.
# To access per-player-data inside of a function, use the $usearenadata()
#expansion function.

##[param]: type: static or dynamic. by default, static (except as below:)
# if arena data is already defined (through use of dependencies or $lock
#included), the default is to not change whether it is static or dynamic.
# dynamic arena data uses a mechanism to only allocate the full size of the
#struct for the arena when the module is attached. the resulting module will be
#somewhat more complicated.
# this method is especially recommended for modules with very large arena data
#structs, because asss will limited the total number of bytes used for all
#per-arena-data (using the undocumented global setting on load
#General:PerArenaBytes, with a default of 10000.) ACE avoids this problem using
#a wrapper struct.

##
	ArenadataParamEx = re.compile(r'^[ ]?(\w+)?$')
	def handleArenadata(processor, module, params):
		if processor.active_structure:
			raise ProcessingException(processor, 'unexpected $#arenadata')
			
		paramMatch = Processor.ArenadataParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#arenadata')

		type = paramMatch.group(1)
		if type and type <> 'static' and type <> 'dynamic':
			raise ProcessingException(processor,
				'syntax error in $#arenadata: expected: "static" or "dynamic" or nothing as the only parameter')

		if type == 'static' or (not type and not module.per_arena_data):
			module.setupArenaData(dynamic=False)
		elif type == 'dynamic':
			module.setupArenaData(dynamic=True)
		processor.active_structure = module.per_arena_data
		return 'endarenadata' # return the expected follow up directive
		

##directive: endarenadata
# Closes a structure block opened by $#arenadata
##
	def handleEndarenadata(processor, module, params):
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endarenadata')
		processor.active_structure = None
		return None
		

##directive: attach

# Defines a code block for extra code to use during MM_ATTACH.
#End the block with $#endattach

##[param]: type: first or last. by default, first.
# "first" code is executed before callbacks, advisers, commands, and dynamic
#per-player-data is set up for the arena. use $failattach() in an "attach-first"
#block only.
# "last" code is executed after callbacks, advisers, commands, and dynamic
#per-player-data is set up for the arena. however, it is still executed before
#interface implementations are registered for the arena. $failattach() is not
#allowed in an "attach-last" block.

##
	AttachParamEx = re.compile(r'^[ ]?(\w+)?$')
	def handleAttach(processor, module, params):
		paramMatch = Processor.AttachParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor,
				'syntax error in $#attach: expected "first" or "last" or nothing as the only parameter')
		
		type = paramMatch.group(1)
		if type and type == 'last':
			processor.active_extrablock = module.extra_attachlast_code
		else:
			processor.active_extrablock = module.extra_attachfirst_code
		processor.active_extrablock.write('\t\t/* extra-attach block */ {\n')
		module.force_attach = True
		return 'endattach' # return the expected follow up directive
		
		
##directive: endattach
# Closes an extra-code block opened by $#attach
##
	def handleEndattach(processor, module, params):
		if not processor.active_extrablock \
			or (processor.active_extrablock <> module.extra_attachlast_code
				and processor.active_extrablock <> module.extra_attachfirst_code):
					raise ProcessingException(processor, 'unexpected $#endattach')
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endattach')
		processor.active_extrablock.write('\t\t}\n')
		processor.active_extrablock = None
		return None
	

##directive: callback

# Defines a callback and begins an callback block.
#End the block with $#endcallback
# Inside the block, define one function that is to be the registered callback
#function.
# The callback will automatically be registered and unregistered
#in the module code.
# For more information on callbacks, see
#http://bitbucket.org/grelminar/asss/wiki/Callback

##param: scope: global or arena. with global, registers this callback on load
#for all arenas. with arena, registers this callback on attach to an arena.

##param: callbackId: the callback type identifier (for example: CB_PLAYERACTION)

##
	CallbackParamEx = re.compile(r'^ (\w+) (\w+)$')
	def handleCallback(processor, module, params):
		paramMatch = Processor.CallbackParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#callback')

		scope = paramMatch.group(1)
		if scope <> 'global' and scope <> 'arena':
			raise ProcessingException(processor,
				'expected: "global" or "arena" as first parameter to $#callback')
				
		cbId = paramMatch.group(2)
		
		processor.active_callback = module.createCallback(scope, cbId)
		processor.active_callback.file = processor.filename
		processor.active_callback.line_number = processor.current_line
		return 'endcallback' # return the expected follow up directive
		
		
##directive: endcallback
# Closes a callback block opened by $#callback
##
	def handleEndcallback(processor, module, params):
		if not processor.active_callback:
			raise ProcessingException(processor, 'unexpected $#endcallback')
					
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endcallback')
		
		if not processor.active_callback.function:
			raise ProcessingException(processor, 'empty callback block')
		processor.active_callback = None
		return None


##directive: command

# Defines a command and begins a command block.
#End the block with $#endcommand
# Inside the block, define one function that is to be the registered callback
#function.
# You may also place string literals outside of the function block, these will
#be added to the help text for the command.
# The command will automatically be registered and unregistered
#in the module code.

##param: scope: global or arena. with global, registers this command on load
#for all arenas. with arena, registers this command on attach to an arena.

##param: names: the names of the command, separated by commas.
# for example the value "money,funds,m" creates one command with the main name
#?money, and aliases ?funds and ?m

##
	CommandParamEx = re.compile(r'^ (\w+) (.+)$')
	def handleCommand(processor, module, params):
		paramMatch = Processor.CommandParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#command')
			
		scope = paramMatch.group(1)
		if scope <> 'global' and scope <> 'arena':
			raise ProcessingException(processor,
				'expected: "global" or "arena" as first parameter to $#command')
				
		names = paramMatch.group(2)
		processor.active_command = module.createCommand(scope, names)
		processor.active_command.file = processor.filename
		processor.active_command.line_number = processor.current_line
		return 'endcommand' # return the expected follow up directive


##directive: endcommand
# Closes a command block opened by $#command
##
	def handleEndcommand(processor, module, params):
		if not processor.active_command:
			raise ProcessingException(processor, 'unexpected $#endcommand')
					
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endcommand')
				
		processor.active_command = None
		return None


##directive: detach

# Defines a code block for extra code to use during MM_DETACH.
#End the block with $#enddetach

##[param]: type: first or last. by default, last.
# "first" code is executed after interfaces are unregistered, but before
#any other actions. "first" code is not called after a $failattach() directive.
# "last" code is executed after everything is cleaned up except dependency
#pointers and per-arena-data. dynamic per-player-data will already be freed by
#this point. this code will be called after a $failattach() directive.

##
	DetachParamEx = re.compile(r'^[ ]?(\w+)?$')
	def handleDetach(processor, module, params):
		paramMatch = Processor.DetachParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor,
				'syntax error in $#detach: expected "first" or "last" or nothing as the only parameter')
		
		type = paramMatch.group(1)
		if type and type == 'first':
			processor.active_extrablock = module.extra_detachfirst_code
		else:
			processor.active_extrablock = module.extra_detachlast_code
		processor.active_extrablock.write('\t\t/* extra-detach block */ {\n')
		module.force_attach = True
		return 'enddetach' # return the expected follow up directive


##directive: enddetach
# Closes an extra-code block opened by $#detach
##
	def handleEnddetach(processor, module, params):
		if not processor.active_extrablock \
			or (processor.active_extrablock <> module.extra_detachlast_code
				and processor.active_extrablock <> module.extra_detachfirst_code):
					raise ProcessingException(processor,
						'unexpected $#enddetach')
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#enddetach')
		processor.active_extrablock.write('\t\t}\n')
		processor.active_extrablock = None
		return None
	
	
##directive: implement

# Defines an interface implementation, and begins an implementation block.
#End the block with $#endimplement
# Inside the block, functions should be specified in the order as they are
#listed in the interface-type definition (see the relevant header file.)
# The interface implementation that is created will automatically be registered
#and unregistered in the module code.
# For more information on interfaces, see
#http://bitbucket.org/grelminar/asss/wiki/Interface

##param: scope: global or arena. with global, registers this interface
#implementation on load for all arenas. with arena, registers this
#implementation on attach to an arena.

##param: interfaceTypeOrId1: either the struct type (for example: Ichat) or the
#interface identifier (for example: I_CHAT)
# this parameter expects typenames of the form Ifoo or identifiers of the
#form I_FOO.
# if of neither form, this directive will assume that it is a typename

##[param]: interfaceTypeOrId2: if the struct type is specified for
#interfaceTypeOrId1, then this is the interface identifier.
# if the interface identifier is specified for interfaceTypeOrId1, then this is
#the struct type.
# if not specified, defaults to typenames of the form I_FOO (where Ifoo is a
#standard type name), and Ifoo (where I_FOO is a standard interface id.)
# if interfaceTypeOrId1 was not a standard type name, it will default to
#I_FOO, where FOO is interfaceTypeOrId1.

##[param]: implementationName: the name of the implementation. this is only
#presently used in asss for the rare instances of mm->GetInterfaceByName.
#by default, the name is foo-moduleName where foo is the the lowercase interface
#type (sans a leading I if of the form Ifoo)

##
	ImplementParamEx = re.compile(r'^ (\w+) ([^ ]+)[ ]?([^ ]+)?[ ]?(.+)?$')
	def handleImplement(processor, module, params):
		paramMatch = Processor.ImplementParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#implement')
		
		scope = paramMatch.group(1)
		if scope <> 'global' and scope <> 'arena':
			raise ProcessingException(processor,
				'expected: "global" or "arena" as first parameter to $#implement')
		
		intTypeOrId1 = paramMatch.group(2)
		if not intTypeOrId1:
			raise ProcessingException(processor,
				'expected: second paramater for interface type or id in $#implement')
		intType = None
		intId = None
		outOfConvention = False
		
		if intTypeOrId1[0:2] == 'I_':
			intId = intTypeOrId1
		elif intTypeOrId1[0] == 'I':
			intType = intTypeOrId1
		else:
			outOfConvention = True
			intType = intTypeOrId1
			
		intTypeOrId2 = paramMatch.group(3)
		if intTypeOrId2:
			if intId:
				intType = intTypeOrId2
			else:
				intId = intTypeOrId2
		else:
			if outOfConvention:
				intId = 'I_' + intType.upper()
			elif intType:
				intId = 'I_' + intType[1:].upper()
			else:
				intType = 'I' + intId[2:].lower()
				
		intName = paramMatch.group(4)
		if not intName:
			if outOfConvention:
				intName = intType.lower() + '-' + module.name
			else:
				intName = intType[1:].lower() + '-' + module.name
				
		processor.active_interface = module.createImplementation(scope, \
			intType, intId, intName)
		processor.active_interface.file = processor.filename
		processor.active_interface.line_number = processor.current_line
		
		return 'endimplement' # return the expected follow up directive

		
##directive: endimplement
# Closes an implementation block opened by $#implement
##
	def handleEndimplement(processor, module, params):
		if not processor.active_interface:
			raise ProcessingException(processor, 'unexpected $#endimplement')
					
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endimplement')
				
		processor.active_interface = None
		return None


##directive: load

# Defines a code block for extra code to use during MM_LOAD.
#End the block with $#endload

##[param]: type: first or last. by default, first.
# "first" code is executed before callbacks, advisers, and commands are set up.
#use $failload() in a "load-first" block only.
# "last" code is executed after callbacks, advisers, and commands are set up.
#however, it is still executed before interface implementations are registered.
#$failload() is not allowed in a "load-last" block.

##
	LoadParamEx = re.compile(r'^[ ]?(\w+)?$')
	def handleLoad(processor, module, params):
		paramMatch = Processor.LoadParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor,
				'syntax error in $#load: expected "first" or "last" or nothing as the only parameter')
		
		type = paramMatch.group(1)
		if type and type == 'last':
			processor.active_extrablock = module.extra_loadlast_code
		else:
			processor.active_extrablock = module.extra_loadfirst_code
		processor.active_extrablock.write('\t\t/* extra-load block */ {\n')
		return 'endload' # return the expected follow up directive
	
	
##directive: endload
# Closes an extra-code block opened by $#load
##
	def handleEndload(processor, module, params):
		if not processor.active_extrablock \
			or (processor.active_extrablock <> module.extra_loadlast_code
				and processor.active_extrablock <> module.extra_loadfirst_code):
					raise ProcessingException(processor, 'unexpected $#endload')
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endload')
		processor.active_extrablock.write('\t\t}\n')
		processor.active_extrablock = None
		return None


##directive: module

# Defines the name of the module. There must be a $#module directive on the
#first line of an ACE module, and there may only be one $#module directive in
#the module.

##param: name: the name of the module. this will appear in log entries generated
#by the module, and also create a constant MODULE_NAME. must use alphanumeric
#characters and _ only.

##
	ModuleParamEx = re.compile(r'^ (\w+)$')
	def handleModule(processor, module, params):
		if module.name:
			raise ProcessingException(processor,
				'unexpected $#module, $#module is only allowed on first line of module')
				
		paramMatch = Processor.ModuleParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#module: requires alphanumeric name as only parameter')
			
		module.name = paramMatch.group(1)
		return None
		

##directive: playerdata

# Defines the per-player-data structure for the module; starts a structure
#block. End the block with $#endplayerdata
# Inside the block, define structure fields normally.
# Only one player data structure may be defined in a module, multiple playerdata
#directives just add extra members to the same struct.
# To access per-player-data inside of a function, use the $useplayerdata()
#expansion function.

##[param]: type: static or dynamic. by default, static. if player data is
#already defined, and this parameter is not specified, it will not change
#whether it is static or dynamic.
# dynamic player data uses a mechanism to only allocate the full size of the
#struct for the player when the player is in an arena the module is attached in.
# this method is especially recommended for modules with very large player data
#structs, because asss will limited the total number of bytes used for all
#per-player-data (using the undocumented global setting on load
#General:PerPlayerBytes, with a default of 4000) ACE avoids this problem using
#a wrapper struct.

##
	PlayerdataParamEx = re.compile(r'^[ ]?(\w+)?$')
	def handlePlayerdata(processor, module, params):
		if processor.active_structure:
			raise ProcessingException(processor, 'unexpected $#playerdata')
			
		paramMatch = Processor.PlayerdataParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#playerdata')
		
		type = paramMatch.group(1)
		if type and type <> 'static' and type <> 'dynamic':
			raise ProcessingException(processor,
				'syntax error in $#playerdata: expected: "static" or "dynamic" or nothing as the only parameter')
		
		if type == 'static' or (not type and not module.per_player_data):
			module.setupPlayerData(dynamic=False)
		else:
			module.setupPlayerData(dynamic=True)
		processor.active_structure = module.per_player_data
		return 'endplayerdata' # return the expected follow up directive


##directive: endplayerdata
# Closes a structure block opened by $#playerdata
##
	def handleEndplayerdata(processor, module, params):
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endplayerdata')
		processor.active_structure = None
		return None


##directive: require

# Requires a certain interface to be registered, or a certain interface
#implementation (dependency), and creates a pointer to the interface.
# If the interface is not available, the module will fail to load (or attach.)
# For optional interfaces, the $#use directive should be used.

##param: scope: global or arena.
# with global, requests the interface registered for ALLARENAS, and stores the
#pointer as a global.
# for arena, requests the interface on attach registered to the arena, and
#stores the pointer in per-arena-data (access with $usearenadata())

##param: interfaceType: the struct name of the interface. (for example Ichat)

##[param]: pointerName: the variable name to use for the pointer to the
#interface. by default, is foo for a type named Ifoo, or _bar for any other type
#named bar.

##[param]: interfaceIdOrName: the interface identifier or implementation name.
#(for example I_CHAT).
# by default, is derived from the interface type. I_FOO is assumed for types of
#the form Ifoo, and I_BAR is assumed for any other types of the form bar.
#expects identifiers to be in the form I_FOO, otherwise it will assume this is
#an implementation name.

##[param]: interfaceName: the requested implementation name. this is only for
#advanced uses of interfaces.
# if interfaceIdOrName is a name, using this parameter is not allowed.

##
	RequireParamEx = re.compile(r'^ (\w*) (\w*)[ ]?(\w+)?[ ]?(.+)?[ ]?(.+)?$')
	def handleRequire(processor, module, params):
		paramMatch = Processor.RequireParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#require')
			
		scope = paramMatch.group(1)
		if scope <> 'global' and scope <> 'arena':
			raise ProcessingException(processor,
				'expected: "global" or "arena" as first parameter to $#require')

		intType = paramMatch.group(2)
		
		pointer = paramMatch.group(3)
		if not pointer:
			pointer = intType[1:]

		intIdOrName = paramMatch.group(4)
		intId = None
		intName = None
		if not intIdOrName:
			if intType[0] == 'I':
				intId = 'I_' + intType[1:].upper()
			else:
				intId = 'I_' + intType.upper()
		else:
			if intIdOrName[0:2] == 'I_':
				intId = intIdOrName
			else:
				intName = intIdOrName
				
		intNameParam = paramMatch.group(5)
		if intNameParam:
			if intName:
				raise ProcessingException(processor,
					'interface name specified twice in $#require')
			intName = intNameParam

		dep = module.createDependency(scope, intType, pointer, intId, intName,
			False, processor.filename, processor.current_line)

		return None


##directive: unload

# Defines a code block for extra code to use during MM_UNLOAD.
#End the block with $#endunload

##[param]: type: first or last. by default, last.
# "first" code is executed after interfaces are unregistered, but before
#any other actions. "first" code is not called after a $failload() directive.
# "last" code is executed after everything is cleaned up except dependency
#pointers, per-player-data and per-arena-data. this code will be called after a
#$failload() directive.

##
	UnloadParamEx = re.compile(r'^[ ]?(\w+)?$')
	def handleUnload(processor, module, params):
		paramMatch = Processor.UnloadParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor,
				'syntax error in $#unload: expected "first" or "last" or nothing as the only parameter')
		
		type = paramMatch.group(1)
		if type and type == 'first':
			processor.active_extrablock = module.extra_unloadfirst_code
		else:
			processor.active_extrablock = module.extra_unloadlast_code
		processor.active_extrablock.write('\t\t/* extra-unload block */ {\n')
		return 'endunload' # return the expected follow up directive


##directive: endunload
# Closes an extra-code block opened by $#unload
##
	def handleEndunload(processor, module, params):
		if not processor.active_extrablock \
			or (processor.active_extrablock <> module.extra_unloadlast_code
				and processor.active_extrablock <> module.extra_unloadfirst_code):
					raise ProcessingException(processor,
						'unexpected $#endunload')
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $#endunload')
		processor.active_extrablock.write('\t\t}\n')
		processor.active_extrablock = None
		return None


##directive: use

# Requests a certain interface to be used if registered, or a certain interface
#implementation (dependency), and creates a pointer to the interface.
# If the interface is not
#available, the module will continue loading/attaching as normal, and the
#pointer will be null.
# For interfaces that must be available, use the $#require directive instead.

##param: scope: global or arena.
# with global, requests the interface registered for ALLARENAS, and stores the
#pointer as a global.
# for arena, requests the interface on attach registered to the arena, and
#stores the pointer in per-arena-data (access with $usearenadata())

##param: interfaceType: the struct name of the interface. (for example Ichat)

##[param]: pointerName: the variable name to use for the pointer to the
#interface. by default, is foo for a type named Ifoo, or _bar for any other type
#named bar.

##[param]: interfaceIdOrName: the interface identifier or implementation name.
#(for example I_CHAT).
# by default, is derived from the interface type. I_FOO is assumed for types of
#the form Ifoo, and I_BAR is assumed for any other types of the form bar.
#expects identifiers to be in the form I_FOO, otherwise it will assume this is
#an implementation name.

##[param]: interfaceName: the requested implementation name. this is only for
#advanced uses of interfaces.
# if interfaceIdOrName is a name, using this parameter is not allowed.

##
	UseParamEx = re.compile(r'^ (\w*) (\w*)[ ]?(\w+)?[ ]?(.+)?[ ]?(.+)?$')
	def handleUse(processor, module, params):
		paramMatch = Processor.UseParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor, 'syntax error in $#use')
			
		scope = paramMatch.group(1)
		if scope <> 'global' and scope <> 'arena':
			raise ProcessingException(processor,
				'expected: "global" or "arena" as first parameter to $#use')

		intType = paramMatch.group(2)
		
		pointer = paramMatch.group(3)
		if not pointer:
			pointer = intType[1:]

		intIdOrName = paramMatch.group(4)
		intId = None
		intName = None
		if not intIdOrName:
			if intType[0] == 'I':
				intId = 'I_' + intType[1:].upper()
			else:
				intId = 'I_' + intType.upper()
		else:
			if intIdOrName[0:2] == 'I_':
				intId = intIdOrName
			else:
				intName = intIdOrName
				
		intNameParam = paramMatch.group(5)
		if intNameParam:
			if intName:
				raise ProcessingException(processor,
					'interface name specified twice in $#use')
			intName = intNameParam
			
		dep = module.createDependency(scope, intType, pointer, intId, intName,
			True, processor.filename, processor.current_line)		
		return None
		
##inline: failattach

# Used inside of an "attach-first" extra-code block. If this point in the code
#is reached, the module will fail to attach and begin cleaning up any resources
#obtained from the arena up to that point.
# Resources obtained during the "attach-first" block should be freed in an
#"detach-last" block.

##[param]: messageFormat: a printf format string that will be used for the
#message recorded to the log for the reason why the module failed to attach.

##[param]: ...: items required to fill in the pieces of the messageFormat string
#(as many as are needed, separated by commas, just like using printf)

##
	FailattachParamEx = re.compile(r'^\s*(\"[^"]*"\s*(,.+))?\s*$')
	def handleFailattach(processor, module, whitespace, params):
		if not processor.active_extrablock \
			or processor.active_extrablock <> module.extra_attachfirst_code:
			raise ProcessingException(processor,
				'$failattach() encountered outside of attach-first block')
		paramMatch = Processor.FailattachParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor,
				'syntax error in $failattach()')
				
		log = paramMatch.group(1)
		result = None
		if log:
			result = whitespace + 'lm->Log(L_ERROR, "<' + module.name + '> " ' \
				+ log + ');\n' + whitespace + 'failedAttach = TRUE;\n' \
				+ whitespace + 'goto ace_fail_attach;'
		else:
			result = whitespace + 'failedAttach = TRUE;\n' + whitespace \
				+ 'goto ace_fail_attach;'
		module.force_fail_attach_label = True
		return result
		
		
##inline: failload

# Used inside of a "load-first" extra-code block. If this point in the code is
#reached, the module will fail to load and begin unloading, generally releasing
#any resources it has obtained up to that point.
# Resources obtained during the "load-first" block should be freed in an
#"unload-last" block.

##[param]: messageFormat: a printf format string that will be used for the
#message recorded to the log for the reason why the module failed to load.

##[param]: ...: items required to fill in the pieces of the messageFormat string
#(as many as are needed, separated by commas, just like using printf)

##
	FailloadParamEx = re.compile(r'^\s*(\"[^"]*"\s*(,.+))?\s*$')
	def handleFailload(processor, module, whitespace, params):
		if not processor.active_extrablock \
			or processor.active_extrablock <> module.extra_loadfirst_code:
			raise ProcessingException(processor,
				'$failload() encountered outside of load-first block')
		paramMatch = Processor.FailloadParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor,
				'syntax error in $failload()')
				
		log = paramMatch.group(1)
		result = None
		if log:
			result = whitespace + 'lm->Log(L_ERROR, "<' + module.name + '> " ' \
				+ log + ');\n' + whitespace + 'failedLoad = TRUE;\n' \
				+ whitespace + 'goto ace_fail_load;'
		else:
			result = whitespace + 'failedLoad = TRUE;\n' + whitespace \
				+ 'goto ace_fail_load;'
		module.force_fail_load_label = True
		return result


##inline: lock

# Lock the module's mutex.
# Provides support for an automatic global-level mutex.
# This mutex is recursive, so may be locked multiple times in the same thread
#without blocking. You must call $unlock() an equal number of times to give
#other threads access.
# The mutex is initialized after "load-first" blocks, and may not be accessed
#in load-first blocks. It is destroyed before "unload-last" blocks, and may not
#be accessed in unload-last blocks.
##
	def handleLock(processor, module, whitespace, params):
		if not processor.function_mode and not processor.active_extrablock:
			raise ProcessingException(processor,
				'$lock() appeared outside of a function/extra-code block')
		if processor.active_extrablock == module.extra_unloadlast_code or \
			processor.active_extrablock == module.extra_loadfirst_code:
			raise ProcessingException(processor,
				'$lock() appeared inside of a load-first or unload-last block')

		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $lock()')
		
		module.use_mutex = True
		return whitespace + 'pthread_mutex_lock(&ace_mutex);'


##inline: null

# Used to specify an unimplemented adviser function, substituting NULL into the
#adivser struct for the function pointer.

##
	def handleNull(processor, module, whitespace, params):
		if not processor.active_adviser:
			raise ProcessingException(processor,
				'$null() appeared outside of an adviser block')
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $null()')
		
		processor.active_adviser.functions.append(None)
		
		return ''
	
	
##inline: unlock

# Unlock the module's mutex.
# Provides support for an automatic global-level mutex.
# This mutex is recursive, so may be locked multiple times in the same thread
#without blocking. You must call $unlock() an equal number of times to give
#other threads access.
# The mutex is initialized after "load-first" blocks, and may not be accessed
#in load-first blocks. It is destroyed before "unload-last" blocks, and may not
#be accessed in unload-last blocks.
##
	def handleUnlock(processor, module, whitespace, params):
		if not processor.function_mode and not processor.active_extrablock:
			raise ProcessingException(processor,
				'$unlock() appeared outside of a function/extra-code block')
		noParams = Processor.NoParamEx.match(params)
		if not noParams:
			raise ProcessingException(processor,
				'syntax error: unexpected paramaters in $unlock()')
		
		module.use_mutex = True
		return whitespace + 'pthread_mutex_unlock(&ace_mutex);'


##inline: usearenadata

# Declare a pointer to the arena data struct (defined by $#arenadata, and also
#used to store arena-level interface pointers.)

##param: var: the name of the variable to declare

##param: arena: the pointer to the arena to point to

##
	UsearenadataParamEx = re.compile(r'\s*(.*)\s*,\s*(.*)\s*')
	def handleUsearenadata(processor, module, whitespace, params):
		if not module.per_arena_data:
			raise ProcessingException(processor,
				'$usearenadata() appeared when per-arena-data is not defined for this module')
		paramMatch = Processor.UsearenadataParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor,
				'syntax error in $usearenadata()')
		
		return module.per_arena_data.getInvokeCode(paramMatch.group(1),
			paramMatch.group(2), whitespace)
	

##inline: useplayerdata

# Declare a pointer to the player data struct (defined by $#playerdata.)

##param: var: the name of the variable to declare

##param: player: the pointer to the player to point to

##
	UseplayerdataParamEx = re.compile(r'\s*(.*)\s*,\s*(.*)\s*')
	def handleUseplayerdata(processor, module, whitespace, params):
		if not module.per_player_data:
			raise ProcessingException(processor,
				'$useplayerdata() appeared when per-player-data is not defined for this module')
		paramMatch = Processor.UseplayerdataParamEx.match(params)
		if not paramMatch:
			raise ProcessingException(processor,
				'syntax error in $useplayerdata()')
		
		return module.per_player_data.getInvokeCode(paramMatch.group(1),
			paramMatch.group(2), whitespace)

	
	def __init__(self, filename, module):
		self.filename = filename
		self.module = module
		self.file_handle = open(filename, 'r')
		self.current_line = 0
		self.expected_directive = 'module'
		
		self.active_extrablock = None
		self.active_interface = None
		self.active_callback = None
		self.active_adviser = None
		self.active_command = None
		self.active_structure = None
		self.function_mode = False
		
		self.use_line_directives = False

	def registerFunction(self, function):
		self.module.functions.append(function)
		if self.active_interface:
			self.active_interface.functions.append(function)
		elif self.active_adviser:
			self.active_adviser.functions.append(function)
		elif self.active_callback:
			if self.active_callback.function:
				raise ProcessingException(self, \
					'two functions in $#callback block')
			self.active_callback.function = function
		elif self.active_command:
			if self.active_command.function:
				raise ProcessingException(self, \
					'two functions in $#command block')
			self.active_command.function = function

	def addLineDirectives(self, line):
		if self.use_line_directives and self.needs_line_directive:
			line_directive = '\n#line ' + str(self.current_line) + ' "' \
				+ self.filename + '"\n'
			if line.find('\n', 0, -1) != -1:
				multiline = line[0:-1].split('\n')
				line = ''
				for L in multiline:
					line = line + line_directive + L
				line = line + '\n'
			elif line <> '\n' and line <> '\r\n':
				line = line_directive + line
		return line

	def process(self):
		buffer = StringIO()
		function_start = 0
		new_line_previously = False
		self.needs_line_directive = False
		
		for line in self.file_handle:
			used_inline = False
			self.current_line += 1
			
			if not self.function_mode and (line == '\n' or line == '\r\n'):
				if new_line_previously:
					self.needs_line_directive = True
					continue
				new_line_previously = True
			else:
				new_line_previously = False
				
			inline = Processor.InlineEx.match(line)
			if inline:
				initialWhitespace = inline.group(1)
				if not initialWhitespace:
					initialWhitespace = ''
				if self.active_extrablock:
					initialWhitespace = '\t\t' + initialWhitespace
				inlineName = inline.group(2)
				inlineParams = inline.group(3)
				extraJunk = inline.group(4)

				if inlineName in InlineHandlers:
					line = InlineHandlers[inlineName](self, \
						self.module, initialWhitespace, inlineParams) \
						+ extraJunk + '\n'
					if line.find('\n', 0, -1) != -1:
						self.needs_line_directive = True
					used_inline = True
				else:
					raise ProcessingException(self,
						'unknown inline function $' + inlineName + '()')

			if self.function_mode or self.active_extrablock:
				interfacesUsed = Processor.InterfaceUsageEx.findall(line)
				if interfacesUsed:
					for key in interfacesUsed:
						if key in ACEModule.autoInterfaces:
							self.module.addAutoDependency(key)
							
			if not self.function_mode:
				directive = Processor.DirectiveEx.match(line)
				if directive:
					directiveName = directive.group(1)
					directiveParams = directive.group(2)
					if self.expected_directive \
						and self.expected_directive != directiveName \
						and directiveName:
						raise ProcessingException(self,
							'only valid directive here is a $#' +
							self.expected_directive + ' directive, encountered "' +
							directiveName + '"')
			
					if directiveName in DirectiveHandlers:
						self.expected_directive = DirectiveHandlers[directiveName]( \
							self, self.module, directiveParams)
						self.needs_line_directive = True
						continue
					else:
						raise ProcessingException(self,
							'unknown directive $#' + directiveName)
						includeCheck = ACEModule.includeCRegex.match(line)
				
				cpp = Processor.CPreprocessorEx.match(line)
				if cpp:
					if cpp.group(1) == 'include':
						include = cpp.group(2)
						self.module.includes[include] = include
						continue
					elif cpp.group(1) == 'define':
						self.module.defines[cpp.group(2)] = cpp.group(3)
					continue
			
			else:
				line = self.addLineDirectives(line)
				buffer.write(line)
				self.needs_line_directive = False
				function_end = ACEFunction.FunctionEndEx.match(line)
				if function_end:
					function_definition = ACEFunction.FunctionCompleteEx.search(buffer.getvalue())
					if function_definition:
						newFn = ACEFunction(function_definition.group(2), function_definition.group(3), function_definition.group(4), function_definition.group(5))
						if self.use_line_directives:
							newFn.file = self.filename
							newFn.line_number = function_start
						self.registerFunction(newFn)
						self.function_mode = False
						buffer.truncate(0)
						self.needs_line_directive = True
					else:
						raise ProcessingException(self,
							'syntax error in function definition. check to make sure your function is declared properly')
				continue
				
			if self.current_line == 1:
				raise ProcessingException(self, '$#module not on first line')

			if not self.active_extrablock and not self.active_structure:
				function_part = ACEFunction.FunctionDeclareEx.match(line)
				if function_part:
					# we are capturing a function, when we get the complete function
					# we will flush the buffer. until then, wait for the next line
					self.function_mode = True
					function_start = self.current_line
					line = self.addLineDirectives(line)
					buffer.write(line)
					self.needs_line_directive = False
					continue
					
				struct_begin = ACEStructure.StructDeclareEx.match(line)
				if struct_begin:
					self.active_structure = ACEStructure(self.module, struct_begin.group(2))
					if self.use_line_directives:
						self.active_structure.line_number = self.current_line
						self.active_structure.file = self.filename
					continue
					
				typedef_declare = ACEStructure.TypedefDeclareEx.match(line)
				if typedef_declare:
					if self.use_line_directives:
						self.module.typedefs.append((self.filename, self.current_line, typedef_declare.group(1)))
					else:
						self.module.typedefs.append((None, None, typedef_declare.group(1)))
					continue

			if self.active_structure:
				if self.active_structure.closeviaregex:
					ignore_line = ACEStructure.StructDeclareExtraEx.match(line)
					if ignore_line:
						continue
						
					end_struct = ACEStructure.StructEndEx.match(line)
					if end_struct:
						if end_struct.group(1):
							if self.active_structure.name and self.active_structure.name != end_struct.group(1):
								raise ProcessingException(self, 'struct name inconsistency, check to make sure the struct is named as you want it')
							self.active_structure.name = end_struct.group(1)
						self.module.structs.append(self.active_structure)
						self.active_structure = False
						continue

				itemSpecified = ACEStructure.StructFieldEx.match(line)
				if itemSpecified:
					self.active_structure.pushItem(self.filename, self.current_line, itemSpecified.group(1))
				continue
			elif self.active_command:
				string_capture = Processor.StringEx.match(line)
				if string_capture:
					if self.use_line_directives and self.needs_line_directive:
						self.active_command.addHelpLine(string_capture.group(1),
							self.filename, self.current_line)
						self.needs_line_directive = False
					else:
						self.active_command.addHelpLine(string_capture.group(1))
				else:
					self.needs_line_directive = True
				continue
					
			if self.active_extrablock and not used_inline:
				line = '\t\t' + line

			line = self.addLineDirectives(line)
			self.needs_line_directive = False
					
			if self.active_extrablock:
				self.active_extrablock.write(line)
			else:
				if line <> '\n' and line <> '\r\n':
					self.module.writeCode(line)

		if self.function_mode:
			raise ProcessingException(self,
				'expected unindented } before end of file to close a function')
		if self.expected_directive:
			raise ProcessingException(self,
				'expected $#' + self.expected_directive + ' before end of file')


DirectiveHandlers = {'adviser': Processor.handleAdviser,
	'endadviser': Processor.handleEndadviser,
	'arenadata': Processor.handleArenadata,
	'endarenadata': Processor.handleEndarenadata,
	'attach': Processor.handleAttach,
	'endattach': Processor.handleEndattach,
	'callback': Processor.handleCallback,
	'endcallback': Processor.handleEndcallback,
	'command': Processor.handleCommand,
	'endcommand': Processor.handleEndcommand,
	'detach': Processor.handleDetach,
	'enddetach': Processor.handleEnddetach,
	'implement': Processor.handleImplement,
	'endimplement': Processor.handleEndimplement,
	'load': Processor.handleLoad,
	'endload': Processor.handleEndload,
	'module': Processor.handleModule,
	'playerdata': Processor.handlePlayerdata,
	'endplayerdata': Processor.handleEndplayerdata,
	'require': Processor.handleRequire,
	'unload': Processor.handleUnload,
	'endunload': Processor.handleEndunload,
	'use': Processor.handleUse
}

InlineHandlers = {'null': Processor.handleNull,
	'lock': Processor.handleLock,
	'unlock': Processor.handleUnlock,
	'failload': Processor.handleFailload,
	'failattach': Processor.handleFailattach,
	'usearenadata': Processor.handleUsearenadata,
	'useplayerdata': Processor.handleUseplayerdata
}

class ACEModule:

	autoInterfaces = {'chat': ('Ichat', 'I_CHAT'),
			'cfg': ('Iconfig', 'I_CONFIG'),
			'cmd': ('Icmdman', 'I_CMDMAN'),
			'game': ('Igame', 'I_GAME'),
			'aman': ('Iarenaman', 'I_ARENAMAN'),
			'pd': ('Iplayerdata', 'I_PLAYERDATA'),
			'ml': ('Imainloop', 'I_MAINLOOP'),
			'prng': ('Iprng', 'I_PRNG'),
			'net': ('Inet', 'I_NET')
	}

	def __init__(self):
		self.name = None

		self.use_line_directives = False
		
		self.midcode = StringIO()
		self.extra_loadfirst_code = StringIO()
		self.extra_unloadfirst_code = StringIO()
		self.extra_attachfirst_code = StringIO()
		self.extra_detachfirst_code = StringIO()
		self.extra_loadlast_code = StringIO()
		self.extra_unloadlast_code = StringIO()
		self.extra_attachlast_code = StringIO()
		self.extra_detachlast_code = StringIO()

		self.force_attach = False
		self.force_fail_load_label = False
		self.force_fail_attach_label = False
		
		self.per_arena_data = None
		self.per_player_data = None
		self.use_mutex = None
		
		self.includes = {'<stdio.h>': '<stdio.h>'}
		self.defines = {}
		self.typedefs = []
		self.structs = []
		self.functions = []
		
		self.global_dependencies = {'lm': ACEDependency(self, 'Ilogman', 'lm',
			'I_LOGMAN')
		}
		
		self.optional_global_dependencies = {}
	
		self.arena_dependencies = {}
		self.optional_arena_dependencies = {}
	
		self.my_global_advisers = []
		self.my_global_callbacks = []
		self.my_global_interfaces = []
		self.my_global_commands = []
	
		self.my_arena_advisers = []
		self.my_arena_callbacks = []
		self.my_arena_interfaces = []
		self.my_arena_commands = []
		
		self.internal_arena_callbacks = []

	def writeCode(self, code):
		self.midcode.write(code)
		
	def createAdviser(self, scope, advType, advId, line=None):
		newAdv = ACEAdviser(self, advType, advId)
		newAdv.line = None
		if scope <> 'arena':
			self.my_global_advisers.append(newAdv)
		else:
			self.my_arena_advisers.append(newAdv)
		return newAdv
		
	def createCallback(self, scope, cbId):
		newCb = ACECallback(self, cbId)
		if scope <> 'arena':
			self.my_global_callbacks.append(newCb)
		else:
			self.my_arena_callbacks.append(newCb)
		return newCb
			
	def createCommand(self, scope, names):
		namesList = names.split(',')
		newCmd = ACECommand(self, namesList)
		if scope <> 'arena':
			self.my_global_commands.append(newCmd)
		else:
			self.my_arena_commands.append(newCmd)

		self.addAutoDependency('cmd')
		return newCmd


	def createDependency(self, scope, intType, pointer, intId, intName, optional, file=None, line=None):
		newDep = ACEDependency(self, intType, pointer, intId, intName)
		newDep.file = file
		newDep.line_number = line
		if scope <> 'arena':
			if not optional:
				self.global_dependencies[newDep.pointer] = newDep;
			else:
				self.optional_global_dependencies[newDep.pointer] = newDep;
		else:
			if not optional:
				self.arena_dependencies[newDep.pointer] = newDep;
			else:
				self.optional_arena_dependencies[newDep.pointer] = newDep;
			if not self.per_arena_data:
				self.per_arena_data = ACEArenaData(self)
			self.per_arena_data.pushItem(file, line, newDep.type + ' *' + newDep.pointer)
		return newDep
			
	def createImplementation(self, scope, intType, intId, intName):
		newInt = ACEInterface(self, intType, intId, intName)
		if scope <> 'arena':
			self.my_global_interfaces.append(newInt)
		else:
			self.my_arena_interfaces.append(newInt)
		return newInt
	
	def setupArenaData(self, dynamic=False):
		if not self.per_arena_data:
			self.per_arena_data = ACEArenaData(self, dynamic)
		else:
			if dynamic <> None:
				self.per_arena_data.dynamic = dynamic
		self.addAutoDependency('aman')

	def setupPlayerData(self, dynamic=False):
		if not self.per_player_data:
			self.per_player_data = ACEPlayerData(self, dynamic)
			if dynamic:
				newfnbody = '\n\tif (action == PA_PREENTERARENA && arena->status <= ARENA_RUNNING)\n\t{\n' + self.per_player_data.getWrapperInvokeCode('pdata', 'p', '\t\t') + '\t\twrapped_pdata->data = amalloc(sizeof(*wrapped_pdata));\n'
				newfnbody += '\t}\n\telif (action == PA_LEAVEARENA)\n\t{\n' + self.per_player_data.getInvokeCode('pdata', 'p', '\t\t') + '\n\t\twrapped_pdata->data = NULL;\n\t\tafree(pdata);\n\t}\n'
				newfn = ACEFunction('void', 'ace_playeraction', 'Player *p, int action, Arena *arena', newfnbody)
				newfn.body = newfnbody
				self.functions.append(newfn)
				newcb = ACECallback(self, 'CB_PLAYERACTION')
				newcb.function = newfn
				self.internal_arena_callbacks.append(newcb)
		else:
			self.per_player_data.dynamic = dynamic

		self.addAutoDependency('pd')
	
	def isAttachable(self):
		if self.force_attach:
			return True
		if self.force_fail_attach_label:
			return True
		if self.per_arena_data:
			if self.per_arena_data.dynamic == True:
				return True
		if self.per_player_data:
			if self.per_player_data.dynamic == True:
				return True			
		if len(self.arena_dependencies) > 0:
			return True
		if len(self.optional_arena_dependencies) > 0:
			return True
		if len(self.my_arena_advisers) > 0:
			return True
		if len(self.my_arena_callbacks) > 0:
			return True
		if len(self.my_arena_interfaces) > 0:
			return True
		if len(self.my_arena_commands) > 0:
			return True
		return False
		
	def useFailLoadLabel(self):
		if self.force_fail_load_label:
			return True
		if len(self.global_dependencies) > 1: #we always use lm and don't goto from there
			return True
		if self.per_arena_data:
			return True
		if self.per_player_data:
			return True
		for dep in self.optional_global_dependencies:
			if dep.identifier and dep.name:
				return True
		return False
		
	def useFailAttachLabel(self):
		if self.force_fail_attach_label:
			return True
		if len(self.arena_dependencies) > 0:
			return True
		return False
		
	def needArenaDataInEntryPoint(self):
		if self.per_arena_data and self.per_arena_data.dynamic == True:
			return True
		if len(self.arena_dependencies) > 0 \
			or len(self.optional_arena_dependencies) > 0:
			return True
		return False

	def addAutoDependency(self, key):
		if key in self.global_dependencies or key in self.optional_global_dependencies:
			return
		type, identifier = ACEModule.autoInterfaces[key]
		self.global_dependencies[key] = ACEDependency(self, type, key, identifier)
		
	def writeOut(self):
		print '#include "asss.h"'
		
		print

		for value in self.includes.values():
			print '#include', value
		
		for key, value in self.defines.iteritems():
			print '#define', key, value
		
		for file, line, typedef in self.typedefs:
			if file and line:
				print '#line %i "%s"' % (line, file)
			print 'typedef', typedef + ';'
			
		for struct in self.structs:
			struct.printDeclareCode()
			print

		print
		
		print 'local Imodman *mm;'
		for key, dep in self.global_dependencies.items():
			dep.printDeclareCode()
		for key, dep in self.optional_global_dependencies.items():
			dep.printDeclareCode()
		
		print 
		
		for cmd in self.my_global_commands:
			cmd.printDeclareCode()
		for cmd in self.my_arena_commands:
			cmd.printDeclareCode()
			
		for fn in self.functions:
			print fn.prototype()
		print
			
		for int in self.my_global_interfaces:
			int.printDeclareCode()
		for int in self.my_arena_interfaces:
			int.printDeclareCode()
		for adv in self.my_global_advisers:
			adv.printDeclareCode()
		for adv in self.my_arena_advisers:
			adv.printDeclareCode()
			
		if self.per_arena_data:
			print
			self.per_arena_data.printDeclareCode()

		if self.per_player_data:
			print
			self.per_player_data.printDeclareCode()

		if self.use_mutex:
			print '\nlocal pthread_mutex_t ace_mutex;'
			
		print self.midcode.getvalue()

		for fn in self.functions:
			print fn.code()
		
		# entry point function
		if self.use_line_directives:
			print '#line 1 "' + self.source_file + '"'

		print 'EXPORT int MM_' + self.name + '(int action, Imodman *_mm, Arena *arena)\n{'
		
		# MM_LOAD
		if self.useFailLoadLabel():
			print '\tint failedLoad = FALSE;'
		if self.useFailAttachLabel():
			print '\tint failedAttach = FALSE;'

		print '\tif (action == MM_LOAD)\n\t{'
		if self.use_mutex:
			print '\t\tpthread_mutexattr_t attr;'
		print '\n\t\tmm = _mm;'
		print '\t\tlm = mm->GetInterface(I_LOGMAN, ALLARENAS);'
		print '\t\tif (!lm)\n\t\t{'
		print '\t\t\tfprintf(stderr, "<' + self.name + '> error obtaining required interface I_LOGMAN " I_LOGMAN);'
		print '\t\t\treturn MM_FAIL;'
		print '\t\t}'
		
		for key, dep in self.global_dependencies.items():
			if key == 'lm':
				continue
			dep.printLoadCode(failGracefully=False)

		for key, dep in self.optional_global_dependencies.items():
			dep.printLoadCode(failGracefully=True)

		if self.per_arena_data:
			self.per_arena_data.printLoadCode()
			
		if self.per_player_data:
			self.per_player_data.printLoadCode()
			
		print self.extra_loadfirst_code.getvalue()

		if self.use_mutex:
			print '\t\tpthread_mutexattr_init(&attr);'
			print '\t\tpthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);'
			print '\t\tpthread_mutex_init(&ace_mutex, &attr);'
			print '\t\tpthread_mutexattr_destroy(&attr);'
	
		for cb in self.my_global_callbacks:
			cb.printLoadCode()
			
		for adv in self.my_global_advisers:
			adv.printLoadCode()

		for cmd in self.my_global_commands:
			cmd.printLoadCode()
						
		print self.extra_loadlast_code.getvalue()
		
		for int in self.my_global_interfaces:
			int.printLoadCode()
		
		print '\t\treturn MM_OK;'
		print '\t}'
		
		# MM_UNLOAD
		print '\telse if (action == MM_UNLOAD)\n\t{'
		
		for int in self.my_global_interfaces:
			int.printUnloadCode()
			
		print self.extra_unloadfirst_code.getvalue()
			
		for cmd in self.my_global_commands:
			cmd.printUnloadCode()
			
		for adv in self.my_global_advisers:
			adv.printUnloadCode()
			
		for cb in self.my_global_callbacks:
			cb.printUnloadCode()
			
		if self.use_mutex:
			print '\t\tpthread_mutex_destroy(&ace_mutex);'
			
		if self.useFailLoadLabel():
			print 'ace_fail_load:'
		
		print self.extra_unloadlast_code.getvalue()
		
		if self.per_player_data:
			self.per_player_data.printUnloadCode()
				
		if self.per_arena_data:
			self.per_arena_data.printUnloadCode()
			
		for key, dep in self.global_dependencies.items():
			dep.printUnloadCode()

		for key, dep in self.optional_global_dependencies.items():
			dep.printUnloadCode()
		
		if self.useFailLoadLabel():
			print '\t\tif (failedLoad)\n\t\t\treturn MM_FAIL;\n\t\telse\n\t',
		print '\t\treturn MM_OK;'
		print '\t}'
		
		if self.isAttachable():
			# MM_ATTACH
			print '\telse if (action == MM_ATTACH)\n\t{'

			if self.needArenaDataInEntryPoint():
				self.per_arena_data.printAttachCode()
		
			for key, dep in self.arena_dependencies.items():
				dep.printAttachCode(failGracefully=False)

			for key, dep in self.optional_arena_dependencies.items():
				dep.printAttachCode(failGracefully=True)

			print self.extra_attachfirst_code.getvalue()
			
			for cb in self.internal_arena_callbacks:
				cb.printAttachCode()
				
			if self.per_player_data:
				self.per_player_data.printAttachCode()
		
			for cb in self.my_arena_callbacks:
				cb.printAttachCode()	

			for adv in self.my_arena_advisers:
				adv.printAttachCode()
								
			for cmd in self.my_arena_commands:
				cmd.printAttachCode()
			
			print self.extra_attachlast_code.getvalue()
						
			for int in self.my_arena_interfaces:
				int.printAttachCode()
			
			print '\t\treturn MM_OK;'
			print '\t}'
		
			# MM_DETACH
			print '\telse if (action == MM_DETACH)\n\t{'

			if self.needArenaDataInEntryPoint():
				self.per_arena_data.printDetachBeginCode()
				
			for int in self.my_arena_interfaces:
				int.printDetachCode()
				
			print self.extra_detachfirst_code.getvalue()
				
			for cmd in self.my_arena_commands:
				cmd.printDetachCode()
				
			for adv in self.my_arena_advisers:
				adv.printDetachCode()
				
			for cb in self.my_arena_callbacks:
				cb.printDetachCode()
				
			for cb in self.internal_arena_callbacks:
				cb.printDetachCode()

			if self.per_player_data:
				self.per_player_data.printDetachCode()
	
			if self.useFailAttachLabel():
				print 'ace_fail_attach:'
	
			print self.extra_detachlast_code.getvalue()
						
			for key, dep in self.arena_dependencies.items():
				dep.printDetachCode()

			for key, dep in self.optional_arena_dependencies.items():
				dep.printDetachCode()
			
			if self.per_arena_data:
				self.per_arena_data.printDetachFinalCode()
				
			if self.useFailAttachLabel():
				print '\t\tif (failedAttach)\n\t\t\treturn MM_FAIL;\n\t\telse\n\t',
			print '\t\treturn MM_OK;'
			print '\t}'

		# the end
		print '\treturn MM_FAIL;'
	
		print '}\n'
			
class ACEAdviser:
	def __init__(self, module, type, identifier):
		self.module = module
		self.type = type
		self.identifier = identifier
		self.functions = []
		self.var = type.lower() + '_adviser'
		self.file = None
		self.line_number = None
		
	def printDeclareCode(self):
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"' 
		print 'local', self.type, self.var, '=\n{'
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"'
		print '\tADVISER_HEAD_INIT(' + self.identifier + ')'
		for fn in self.functions:
			if fn:
				if self.module.use_line_directives:
					print fn.getLineDirective(),
				print '\t' + fn.name + ','
			else:
				print '\tNULL,'
		print '};'

	def printLoadCode(self):
		print '\t\tmm->RegAdviser(&' + self.var + ', ALLARENAS);'
		
	def printAttachCode(self):
		print '\t\tmm->RegAdviser(&' + self.var + ', arena);'

	def printUnloadCode(self):
		print '\t\tmm->UnregAdviser(&' + self.var + ', ALLARENAS);'
		
	def printDetachCode(self):
		print '\t\tmm->UnregAdviser(&' + self.var + ', arena);'
		
		
class ACECallback:
	def __init__(self, module, identifier):
		self.module = module
		self.identifier = identifier
		self.function = None
		self.file = None
		self.line_number = None
		
	def printLoadCode(self):
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"'
		print '\t\tmm->RegCallback(' + self.identifier + ',', self.function.name + ', ALLARENAS);'
		
	def printUnloadCode(self):
		print '\t\tmm->UnregCallback(' + self.identifier + ',', self.function.name + ', ALLARENAS);'
		
	def printAttachCode(self):
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"'
		print '\t\tmm->RegCallback(' + self.identifier + ',', self.function.name + ', arena);'
		
	def printDetachCode(self):
		print '\t\tmm->UnregCallback(' + self.identifier + ',', self.function.name + ', arena);'
		
		
class ACECommand:
	def __init__(self, module, names):
		self.names = names
		self.helptext = None
		self.function = None
		self.file = None
		self.line_number = None
		self.module = module
		
	def addHelpLine(self, line, file=None, line_number=None):
		if not self.helptext:
			self.helptext = StringIO()
		if file and line_number:
			self.helptext.write('\n#line ' + str(line_number) + ' "' + file + '"')
		self.helptext.write('\n' + line)
		
	def printDeclareCode(self):
		if self.helptext:
			firstname = self.names[0]
			print 'local helptext_t ' + firstname + '_help =',
			print self.helptext.getvalue() + ';\n'
			
	def printLoadCode(self):
		firstname = self.names[0]
		for cmdname in self.names:
			if self.module.use_line_directives and self.file and self.line_number:
				print '#line', self.line_number, '"' + self.file + '"' 
			if self.helptext:
				print '\t\tcmd->AddCommand("' + cmdname + '", ' + self.function.name + ', ALLARENAS, ' + firstname + '_help);'
			else:
				print '\t\tcmd->AddCommand("' + cmdname + '", ' + self.function.name + ', ALLARENAS, NULL);'
				
	def printAttachCode(self):
		firstname = self.names[0]
		for cmdname in self.names:
			if self.module.use_line_directives and self.file and self.line_number:
				print '#line', self.line_number, '"' + self.file + '"' 
			if self.helptext:
				print '\t\tcmd->AddCommand("' + cmdname + '", ' + self.function.name + ', arena, ' + firstname + '_help);'
			else:
				print '\t\tcmd->AddCommand("' + cmdname + '", ' + self.function.name + ', arena, NULL);'
				
	def printUnloadCode(self):
		for cmdname in self.names:
			print '\t\tcmd->RemoveCommand("' + cmdname + '", ' + self.function.name + ', ALLARENAS);'
		
	def printDetachCode(self):
		for cmdname in self.names:
			print '\t\tcmd->RemoveCommand("' + cmdname + '", ' + self.function.name + ', arena);'
			
			
class ACEDependency:
	def __init__(self, module, type, pointer, identifier, name=None):
		self.module = module
		self.name = name
		self.identifier = identifier
		self.pointer = pointer
		self.type = type
		self.optional = False
		self.file = None
		self.line_number = None
		
	def printDeclareCode(self):
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"'
		print 'local', self.type, '*' + self.pointer, '= 0;'

	def printLoadCode(self, arena=None, failGracefully=False):
		if not self.name:
			if self.module.use_line_directives and self.file and self.line_number:
				print '#line', self.line_number, '"' + self.file + '"'
			print '\t\t' + self.pointer, '= mm->GetInterface(' + self.identifier + ', ALLARENAS);'
		
			if not failGracefully:
				print '\t\tif (!' + self.pointer + ')'

				print '\t\t{\n\t\t\tlm->Log(L_ERROR, "<' + self.module.name + '> error obtaining required interface', self.identifier, '"', self.identifier + ');'
				print '\t\t\tfailedLoad = TRUE;'
				print '\t\t\tgoto ace_fail_load;'

				print '\t\t}'
		else:
			if self.module.use_line_directives and self.file and self.line_number:
				print '#line', self.line_number, '"' + self.file + '"'
			print '\t\t' + self.pointer, '= mm->GetInterfaceByName("' + self.name + '");'
			
			if not failGracefully:
				print '\t\tif (!' + self.pointer + ')'

				print '\t\t{\n\t\t\tlm->Log(L_ERROR, "<' + self.module.name + '> error obtaining required named interface', self.name + '");'
				print '\t\t\tfailedLoad = TRUE;'
				print '\t\t\tgoto ace_fail_load;'

				print '\t\t}'
				
			if self.identifier:
				if self.module.use_line_directives and self.file and self.line_number:
					print '#line', self.line_number, '"' + self.file + '"'
				print '\t\tif (strcmp(' + self.pointer + '->head.iid,', self.identifier + '))\n\t\t{'

				print '\t\t\tlm->Log(L_ERROR, "<' + self.module.name + '> named interface', self.name, 'expected interface-id "', self.identifier, '", got %s",', self.pointer + '->head.iid);'
				print '\t\t\tfailedLoad = TRUE;'
				print '\t\t\tgoto ace_fail_load;'

				print '\t\t}'

	def printAttachCode(self, failGracefully=False):
		if not self.name:
			if self.module.use_line_directives and self.file and self.line_number:
				print '#line', self.line_number, '"' + self.file + '"'
			print '\t\tad->' + self.pointer, '= mm->GetInterface(' + self.identifier + ', arena);'
			if not failGracefully:
				print '\t\tif (!ad->' + self.pointer + ')'

				print '\t\t{\n\t\t\tlm->LogA(L_ERROR, "' + self.module.name + '", arena, "error obtaining required interface', self.identifier, '"', self.identifier + ');'
				print '\t\t\tfailedAttach = TRUE;'
				print '\t\t\tgoto ace_fail_attach;'
				
				print '\t\t}'
		else:
			if self.module.use_line_directives and self.file and self.line_number:
				print '#line', self.line_number, '"' + self.file + '"'
			print '\t\tad->' + self.pointer, '= mm->GetInterfaceByName("' + self.name + '");'
			
			if not failGracefully:
				print '\t\tif (!ad->' + self.pointer + ')'

				print '\t\t{\n\t\t\tlm->LogA(L_ERROR, "' + self.module.name + '", arena, "error obtaining required named interface', self.name, '");'
				print '\t\t\tfailedAttach = TRUE;'
				print '\t\t\tgoto ace_fail_attach;'
				
				print '\t\t}'
				
			if self.identifier:
				if self.module.use_line_directives and self.file and self.line_number:
					print '#line', self.line_number, '"' + self.file + '"'
				print '\t\tif (strcmp(ad->' + self.pointer + '->head.iid,', self.identifier + '))\n\t\t{'

				print '\t\t\tlm->LogA(L_ERROR, "' + self.module.name + '", arena, "named interface', self.name, 'expected interface-id "', self.identifier, '", got %s",', self.pointer + '->head.iid);'
				print '\t\t\tfailedAttach = TRUE;'
				print '\t\t\tgoto ace_fail_attach;'
				
				print '\t\t}'
			
	def printUnloadCode(self):
		print '\t\tmm->ReleaseInterface(' + self.pointer + ');'
		
	def printDetachCode(self):
		print '\t\tmm->ReleaseInterface(ad->' + self.pointer +');'
		

class ACEFunction:
	FunctionDeclareEx = re.compile(r'\s*(local)?\s*([A-Za-z0-9_* ]+?)\s*?(\w+?)\((.*?)\)')
	FunctionEndEx = re.compile(r'^}$')
	FunctionCompleteEx = re.compile(r'\s*(local)?\s*([A-Za-z0-9_* ]+?)\s*?(\w+?)\((.*?)\)\s*{(.*)^}', re.DOTALL | re.MULTILINE)
	def __init__(self, declaration, name, params, body):
		self.name = name
		self.declaration = declaration
		self.params = params
		self.body = body
		self.file = None
		self.line_number = None

	def getLineDirective(self):
		if self.file and self.line_number:
			return '#line ' + str(self.line_number) + ' "' + self.file + '"\n'
		return ''
		
	def prototype(self):
		return self.getLineDirective() + 'local ' + self.declaration + ' ' + self.name + '(' + self.params + ');'
		
	def code(self):
		return self.getLineDirective() + self.declaration + ' ' + self.name + '(' + self.params + ')\n{' + self.body + '}\n'
		
				
class ACEInterface:
	def __init__(self, module, type, identifier, name):
		self.module = module
		self.type = type
		self.identifier = identifier
		self.name = name
		self.functions = []
		self.var = name.replace('-', '_').lower() + '_interface'
		self.file = None
		self.line_number = None
		
	def printDeclareCode(self):
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"' 
		print 'local', self.type, self.var, '=\n{'
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"' 
		print '\tINTERFACE_HEAD_INIT(' + self.identifier + ', "' + self.name + '")'
		for fn in self.functions:
			if self.module.use_line_directives:
				print fn.getLineDirective(),
			print '\t' + fn.name + ','
		print '};'
		
	def printLoadCode(self):
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"' 
		print '\t\tmm->RegInterface(&' + self.var + ', ALLARENAS);'
		
	def printAttachCode(self):
		if self.module.use_line_directives and self.file and self.line_number:
			print '#line', self.line_number, '"' + self.file + '"' 
		print '\t\tmm->RegInterface(&' + self.var + ', arena);'

	def printUnloadCode(self):
		print '\t\tif (mm->UnregInterface(&' + self.var + ', ALLARENAS))\n\t\t{'
		print '\t\t\tlm->Log(L_ERROR, "<' + self.module.name + '> unable to unregister', self.var + '");'
		print '\t\t\treturn MM_FAIL;\n\t\t}'
		
	def printDetachCode(self):
		print '\t\tif (mm->UnregInterface(&' + self.var + ', arena))\n\t\t{'
		print '\t\t\tlm->LogA(L_ERROR, "' + self.module.name + '", arena, "unable to unregister', self.var + '");'
		print '\t\t\treturn MM_FAIL;\n\t\t}'

			
class ACEStructure:
	TypedefDeclareEx = re.compile(r'typedef\s*(.*)\s*;$')
	StructDeclareEx = re.compile(r'(typedef)?\s*struct\s*(\w+)')
	StructDeclareExtraEx = re.compile(r'^\s*{\s*$')
	StructEndEx = re.compile(r'^}\s*(\w+)?;\s*$')
	StructFieldEx = re.compile(r'\s*(.+);')

	def __init__(self, module, name, dynamic=False):
		self.module = module
		self.dynamic = dynamic
		self.name = name
		self.items = []
		self.closeviaregex = True
		self.line_number = None
		self.file = None
	
	def pushItem(self, file, line, item):
		self.items.append((file, line, item))
		
	def printDeclareCode(self):
		if self.line_number and self.file:	
			print '#line', self.line_number, '"' + self.file + '"'
		print 'typedef struct', self.name, '\n{'
		
		for file, line, item in self.items:
			if self.module.use_line_directives:
				print '#line', line, '"' + file + '"'
			print '\t' + item + ';'
			
		print '}', self.name + ';'
		
		if self.dynamic:
			print 'typedef struct wrapper_' + self.name + '\n{\n\t' + self.name, '*data;\n} wrapper_' + self.name + ';'

		return


class ACEArenaData(ACEStructure):
	def __init__(self, module, dynamic=False):
		ACEStructure.__init__(self, module, 'arenadata', dynamic)
		self.closeviaregex = False
		
	def printDeclareCode(self):
		print 'local int arenaDataKey = -1;'
		ACEStructure.printDeclareCode(self)

	def printLoadCode(self):
		if not self.dynamic:
			print '\t\t' + 'arenaDataKey = aman->AllocateArenaData(sizeof(' + self.name + '));'
		else:
			print '\t\t' + 'arenaDataKey = aman->AllocateArenaData(sizeof(wrapper_' + self.name + '));'
			
		print '\t\tif (' + 'arenaDataKey == -1)\n\t\t{'
		print '\t\t\tlm->Log(L_ERROR, "<' + self.module.name + '> unable to register arena-data");'
		print '\t\t\tfailedLoad = TRUE;'
		print '\t\t\tgoto ace_fail_load;'
		print '\t\t}'

	def printUnloadCode(self):
		print '\t\tif (' + 'arenaDataKey != -1)'
		print '\t\t\taman->FreeArenaData(arenaDataKey);'
	
	def printAttachCode(self):
		if self.dynamic:
			print '\t\t' + self.name + ' *ad = amalloc(sizeof(*ad));'
			print '\t\twrapper_' + self.name + ' *wrapped_ad = P_ARENA_DATA(arena, arenaDataKey);'
			print '\t\twrapped_ad->data = ad;'
		else:
			print '\t\t' + self.name + ' *ad = P_ARENA_DATA(arena, arenaDataKey);'
		
	def printDetachFinalCode(self):
		if not self.dynamic:
			return;
		print '\t\twrapped_ad->data = NULL;'
		print '\t\tafree(ad);'
		
	def getInvokeCode(self, var, arena, space):
		if not self.dynamic:
			return space + self.name + ' *' + var + ' = ' + arena + ' ? P_ARENA_DATA(' + arena + ', arenaDataKey) : NULL;'
		else:
			return space + 'wrapper_' + self.name + ' *wrapped_' + var + ' = ' + arena + ' ? P_ARENA_DATA(' + arena + ', arenaDataKey) : NULL;\n' + space + self.name + ' *' + var + ' = wrapped_' + var + ' ? wrapped_' + var + '->data : NULL;'

	def printDetachBeginCode(self):
		if not self.dynamic:
			print '\t\t' + self.name + ' *' + 'ad = P_ARENA_DATA(arena, arenaDataKey);'
		else:
			print '\t\twrapper_' + self.name + ' *wrapped_ad = P_ARENA_DATA(arena, arenaDataKey);'
			print '\t\t' + self.name + ' *ad = wrapped_ad->data;\n'


class ACEPlayerData(ACEStructure):
	def __init__(self, module, dynamic=False):
		ACEStructure.__init__(self, module, 'playerdata', dynamic)
		self.closeviaregex = False
		
	def printDeclareCode(self):
		print 'local int playerDataKey = -1;'
		ACEStructure.printDeclareCode(self)

	def printLoadCode(self):
		print '\t\t' + 'playerDataKey = pd->AllocatePlayerData(sizeof(' + self.name + '));'
		print '\t\tif (' + 'playerDataKey == -1)\n\t\t{'
		print '\t\t\tlm->Log(L_ERROR, "<' + self.module.name + '> unable to register player-data");'
		print '\t\t\tfailedLoad = TRUE;'
		print '\t\t\tgoto ace_fail_load;'
		print '\t\t}'

	def printUnloadCode(self):
		print '\t\tif (' + 'playerDataKey != -1)'
		print '\t\t\tpd->FreePlayerData(playerDataKey);'
	
	def printAttachCode(self):
		if self.dynamic:
			print '\t\tpd->Lock();'
			print '\t\t{\n\t\t\tLink *link;'
			print '\t\t\tPlayer *p;'
			print '\t\t\tFOR_EACH_PLAYER_IN_ARENA(p, arena)\n\t\t\t{'
			print self.getWrapperInvokeCode('pdata', 'p', '\t\t\t\t'),
			print '\t\t\t\twrapped_pdata->data = amalloc(sizeof(' + self.name + '));'
			print '\t\t\t}\n\t\t}\n\t\tpd->Unlock();'
		
	def printDetachCode(self):
		if self.dynamic:
			print '\t\tpd->Lock();'
			print '\t\t{\n\t\t\tLink *link;'
			print '\t\t\tPlayer *p;'
			print '\t\t\tFOR_EACH_PLAYER_IN_ARENA(p, arena)\n\t\t\t{'
			print self.getInvokeCode('pdata', 'p', '\t\t\t\t')
			print '\t\t\t\twrapped_pdata->data = NULL;'
			print '\t\t\t\tafree(pdata);'
			print '\t\t\t}\n\t\t}\n\t\tpd->Unlock();'
		
	def getInvokeCode(self, var, player, space):
		if not self.dynamic:
			return space + self.name + ' *' + var + ' = PPDATA(' + player + ', playerDataKey);'
		else:
			return space + 'wrapper_' + self.name + ' *wrapped_' + var + ' = PPDATA(' + player + ', playerDataKey);\n' + space + self.name + ' *' + var + ' = wrapped_' + var + '->data;'

	def getWrapperInvokeCode(self, var, player, space):
		if self.dynamic:
			return space + 'wrapper_' + self.name + ' *wrapped_' + var + ' = PPDATA(' + player + ', playerDataKey);\n'
		else:
			return ''



usage = 'Usage: ace.py [options] input_file'
parser = OptionParser(usage=usage)

parser.add_option("-o", "--output",
	dest="output_file",
	help="output to the specified file")
parser.add_option("-l", "--line-directives",
	dest="use_line_directives",
	action="store_true",
	help="put #line directives in the output to associate output lines with input lines")

(options, in_files) = parser.parse_args()

if len(in_files) == 0:
	sys.stderr.write('error: no input file\n')	
	sys.exit(64)
elif len(in_files) > 1:
	sys.stderr.write('error: more than one input file specified\n')
	sys.exit(64)

in_file = in_files[0]

my_module = ACEModule()
try:
	my_processor = Processor(in_file, my_module)
except IOError, e:
	(errno, message) = e
	sys.stderr.write('%s: error: unable to read file: %s\n' % (in_file, message))
	sys.exit(32)

my_module.source_file = in_file

if options.use_line_directives:
	my_processor.use_line_directives = True
	my_module.use_line_directives = True
	
try:
	my_processor.process()
	if options.output_file:
		try:
			sys.stdout = open(options.output_file, 'w')
		except IOError, e:
			(errno, message) = e
			sys.stderr.write('%s: error: unable to write file: %s\n' % (options.output_file, message))
			sys.exit(16)
	my_module.writeOut()
	sys.exit(0)

except ProcessingException, e:
	sys.stderr.write(e.message())
	sys.stderr.write('\n')
	sys.exit(1)

