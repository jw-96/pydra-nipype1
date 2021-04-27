import pydra
import nipype
import attr
import typing as ty
from copy import deepcopy
import os
from nipype.interfaces.spm.base import SPMCommand
from copy import deepcopy

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

    def _run_task(self):
        print("inside run task:", self.name)
        if not isinstance(self._interface, SPMCommand):
            print(self.name, os.getcwd(), self.output_dir)
            inputs = attr.asdict(self.inputs, filter=lambda a, v: v is not attr.NOTHING)
            node = nipype.Node(self._interface, base_dir=self.output_dir, name=self.name)
            node.inputs.trait_set(**inputs)
            print(self._interface.inputs)
            cmdargs = self._interface.cmdline.split(" ")
            cmd = cmdargs
            print("before")
            docky = pydra.DockerTask(name="docky", executable=cmd, image=self.image, bindings = [ ("/home/jwigger/Documents/", "/home/jwigger/Documents/")], cache_dir = self.output_dir)
            print("after", docky.cmdline)
            res = docky()
            actual_res = res.output.stdout.split("\n")[3:]
            out = "\n".join(actual_res)
            runtime = Runtime(out)
            self.output_ = self._interface.aggregate_outputs(runtime).get()
        else:
            print("SPM", self.name, os.getcwd(), self.output_dir)
            self._interface._matlab_cmd = '/opt/spm12-r7219/run_spm12.sh /opt/matlabmcr-2010a/v713 script'  #= os.environ["SPMMCRCMD"] In the worstcase I just need to run a docker command to get this.
            self._interface._use_mcr = True
            self._interface._check_mlab_inputs()
            self._interface._matlab_cmd_update()
            print(self._interface.mlab.cmd)
            inputs = attr.asdict(self.inputs, filter=lambda a, v: v is not attr.NOTHING)
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
            docky = pydra.DockerTask(name="docky", executable=cmd, image=self.image, bindings = [ ("/home/jwigger/Documents/", "/home/jwigger/Documents/")], cache_dir = self.output_dir)
            print(self.name, "after", docky.cmdline)
            res = docky()
            print(res)
            actual_res = res.output.stdout.split("\n")[3:]
            out = "\n".join(actual_res)
            print(self.name, "out")
            runtime = Runtime(out)
            self._interface.version = "spm12" #TODO read it from out.
            print("VERSION", self._interface.version)
            self.output_ = self._interface.aggregate_outputs(runtime).get()#res.outputs.get()
            print("fin", self.name)
