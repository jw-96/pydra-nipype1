import pydra
import nipype
import attr
import typing as ty
from copy import deepcopy
import os
from nipype.interfaces.spm.base import SPMCommand
from nipype.interfaces.fsl.base import FSLCommand
from copy import deepcopy
from pydra.engine.specs import attr_fields
from pydra.engine.helpers_file import is_existing_file
from pathlib import Path
import shutil
from os.path import join as opj

def traitedspec_to_specinfo(traitedspec):
    trait_names = set(traitedspec.copyable_trait_names())
    return pydra.specs.SpecInfo(
        name="Inputs",
        fields=[
            (name, attr.ib(type=ty.Any, metadata={"help_string": trait.desc}))
            for name, trait in traitedspec.traits().items()
            if name in trait_names
        ],
        bases=(pydra.engine.specs.BaseSpec,),
    )


class Nipype1Task(pydra.engine.task.TaskBase):
    """Wrap a Nipype 1.x Interface as a Pydra Task

    This utility translates the Nipype 1 input and output specs to
    Pydra-style specs, wraps the run command, and exposes the output
    in Pydra Task outputs.

    >>> import pytest
    >>> from pkg_resources import resource_filename
    >>> from nipype.interfaces import fsl
    >>> if fsl.Info.version() is None:
    ...     pytest.skip()
    >>> img = resource_filename('nipype', 'testing/data/tpms_msk.nii.gz')

    >>> from pydra.tasks.nipype1.utils import Nipype1Task
    >>> thresh = Nipype1Task(fsl.Threshold())
    >>> thresh.inputs.in_file = img
    >>> thresh.inputs.thresh = 0.5
    >>> res = thresh()
    >>> res.output.out_file  # DOCTEST: +ELLIPSIS
    '.../tpms_msk_thresh.nii.gz'
    """

    def __init__(
        self,
        interface: nipype.interfaces.base.BaseInterface,
        audit_flags: pydra.AuditFlag = pydra.AuditFlag.NONE,
        image= None,
        cache_dir=None,
        cache_locations=None,
        messenger_args=None,
        messengers=None,
        name=None,
        **kwargs,
    ):
        self.input_spec = traitedspec_to_specinfo(interface.inputs)
        self._interface = interface
        if name is None:
            name = interface.__class__.__name__
        super(Nipype1Task, self).__init__(
            name,
            inputs=kwargs,
            audit_flags=audit_flags,
            messengers=messengers,
            messenger_args=messenger_args,
            cache_dir=cache_dir,
            cache_locations=cache_locations,
        )
        self.output_spec = traitedspec_to_specinfo(interface._outputs())

    def _run_task(self):
        inputs = attr.asdict(self.inputs, filter=lambda a, v: v is not attr.NOTHING)
        # node = nipype.Node(self._interface, base_dir=self.output_dir, name=self.name)
        node = nipype.Node(deepcopy(self._interface), base_dir=self.output_dir, name=self.name)
        node.inputs.trait_set(**inputs)
        res = node.run()
        self.output_ = res.outputs.get()


class Runtime:
    def __init__(self, out):
        self.stdout = out


class Nipype1DockerTask(pydra.engine.task.TaskBase):
    """Wrap a Nipype 1.x Interface as a Pydra Task

    This utility translates the Nipype 1 input and output specs to
    Pydra-style specs, wraps the run command, and exposes the output
    in Pydra Task outputs.

    >>> import pytest
    >>> from pkg_resources import resource_filename
    >>> from nipype.interfaces import fsl
    >>> if fsl.Info.version() is None:
    ...     pytest.skip()
    >>> img = resource_filename('nipype', 'testing/data/tpms_msk.nii.gz')

    >>> from pydra.tasks.nipype1.utils import Nipype1Task
    >>> thresh = Nipype1Task(fsl.Threshold())
    >>> thresh.inputs.in_file = img
    >>> thresh.inputs.thresh = 0.5
    >>> res = thresh()
    >>> res.output.out_file  # DOCTEST: +ELLIPSIS
    '.../tpms_msk_thresh.nii.gz'
    """

    def __init__(
        self,
        interface: nipype.interfaces.base.BaseInterface,
        audit_flags: pydra.AuditFlag = pydra.AuditFlag.NONE,
        image= None,
        cache_dir=None,
        cache_locations=None,
        messenger_args=None,
        messengers=None,
        name=None,
        **kwargs,
    ):
        self.input_spec = traitedspec_to_specinfo(interface.inputs)
        self._interface = interface
        if name is None:
            name = interface.__class__.__name__
        super(Nipype1DockerTask, self).__init__(
            name,
            inputs=kwargs,
            audit_flags=audit_flags,
            messengers=messengers,
            messenger_args=messenger_args,
            cache_dir=cache_dir,
            cache_locations=cache_locations,
        )
        self.output_spec = traitedspec_to_specinfo(interface._outputs())
        self.image = image
        self.bindings = []

    def _run_task(self):
        inputs = attr.asdict(self.inputs, filter=lambda a, v: v is not attr.NOTHING)
        self._create_bindings(inputs)
        self.bindings.append(("/home/jwigger/Documents/", "/home/jwigger/Documents/"))
        print("bindings", self.bindings)
        print("inside run task:", self.name)
        if not isinstance(self._interface, SPMCommand):
            print(self.name, os.getcwd(), self.output_dir)

            node = nipype.Node(self._interface, base_dir=self.output_dir, name=self.name)
            node.inputs.trait_set(**inputs)
            print()
            print(self._interface.cmdline)
            cmdargs = self._interface.cmdline.split(" ")
            cmd = cmdargs
            print("before")
            self.bindings.append((self.output_dir, self.output_dir))
            # The problem: for fsl it creates the outputs in output_dir
            # as the interface reads the current wd and creates the output path
            # which is an argument on the command line.

            # For FSL no output files are specified and it uses cwd at Runtime
            # So the results get written in to the folder of DockerTask
            docky = pydra.DockerTask(name="docky", executable=cmd, image=self.image, bindings = self.bindings, cache_dir = self.output_dir)
            res = docky()
            print("after", docky.cmdline)


            print(self.name, "res", res)
            print()
            print(docky.output_dir)
            parent  = docky.output_dir
            curr  = docky.cache_dir
            dir_list = os.listdir(parent)
            print(dir_list)
            for f in dir_list:
                if f not in ["_task.pklz", "_error.pklz", "_result.pklz"]:
                    print(opj(parent, f), opj(curr, f))
                    shutil.move(opj(parent, f), opj(curr, f))

            if isinstance(self._interface, FSLCommand): #assumes other commands do not run in an docker containing fsl
                out = res.output.stdout.split("\n")[3:]
                out = "\n".join(out)
            else:
                out = res.output.stdout
            print(self.name, "out", out)
            runtime = Runtime(out)
            self.output_ = self._interface.aggregate_outputs(runtime).get()
            print(self.name, "fin")
        else:
            print("SPM", self.name, os.getcwd(), self.output_dir)
            self._interface._matlab_cmd = '/opt/spm12-r7219/run_spm12.sh /opt/matlabmcr-2010a/v713 script'  #= os.environ["SPMMCRCMD"] In the worstcase I just need to run a docker command to get this.
            self._interface._use_mcr = True
            self._interface._check_mlab_inputs()
            self._interface._matlab_cmd_update()
            print(self._interface.mlab.cmd)
            node = nipype.Node(self._interface, base_dir=self.output_dir, name=self.name)
            node.inputs.trait_set(**inputs)
            print(self.name, "set traits")
            self._interface.mlab.inputs.script = self._interface._make_matlab_command(
                deepcopy(self._interface._parse_inputs())
            )
            print(self.name, "after set traits")
            print(self._interface.inputs)
            cmdargs = self._interface.mlab.cmdline.split(" ")
            cmd = cmdargs
            print(self.name, "before", self.image, self._interface.version)
            docky = pydra.DockerTask(name="docky", executable=cmd, image=self.image, bindings = self.bindings, cache_dir = self.output_dir)
            print(self.name, "after", docky.cmdline)
            res = docky()
            print(res)
            out = res.output.stdout
            print(self.name, "out", out)
            runtime = Runtime(out)
            self._interface.version = "spm12" #TODO read it from out.
            print("VERSION", self._interface.version)
            self.output_ = self._interface.aggregate_outputs(runtime).get()#res.outputs.get()
            print("fin", self.name)

    def _create_bindings(self, inputs):
        for k, v in inputs.items():
            print(k,v)
            if is_existing_file(v):
                print("is local", v)
                value = Path(v)
                print(value)
                self.bindings.append((value.parent,value.parent))
            else:
                print("not local")
