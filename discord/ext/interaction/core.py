import inspect
from typing import List, Optional, Union, Callable, Coroutine, Any

from .commands import (
    ApplicationSubcommand,
    ApplicationSubcommandGroup,
    CommandOption,
    SlashCommand,
    UserCommand,
    ContextMenu
)
from .utils import async_all


class BaseCore:
    def __init__(self, func: Callable, checks=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.func = func

        if checks is None:
            checks = []
        if hasattr(func, "__commands_checks__"):
            decorator_checks = getattr(func, "__commands_checks__")
            decorator_checks.reverse()
            checks += decorator_checks
        self.checks: list = checks
        self.cog = None

    def __call__(self, *args, **kwargs):
        return self.callback(*args, **kwargs)

    def callback(self, *args, **kwargs) -> Coroutine[Any, Any, Any]:
        if self.cog is None:
            return self.func(*args, **kwargs)
        return self.func(self.cog, *args, **kwargs)

    async def can_run(self, ctx):
        predicates = self.checks
        if len(predicates) == 0:
            # since we have no checks, then we just return True.
            return True

        return await async_all(predicate(ctx) for predicate in predicates)


# Subcommand
class SubCommand(BaseCore, ApplicationSubcommand):
    def __init__(self, func: Callable, parents, checks=None, *args, **kwargs):
        if kwargs.get("name") is None:
            kwargs["name"] = func.__name__
        self.parents: Union[Command, SubCommandGroup] = parents
        self.top_parents: Command = kwargs.pop("top_parents", self.parents)
        self.parents.options.append(self)

        options = kwargs.get("options")
        if options is None:
            options = []
        if hasattr(func, "__command_options__"):
            func.__command_options__.reverse()
            options += func.__command_options__
        self.base_options = options

        # kwargs['options'] = get_signature_option(func, options)
        super().__init__(func=func, checks=checks, *args, **kwargs)

    def set_signature_option(self) -> None:
        """Since add_interaction is called and cog information is entered in parents,
        parents value is reflected and skipping_argument value is determined.
        """
        if self.top_parents.cog is not None:
            self.options = get_signature_option(
                self.func, self.base_options, skipping_argument=2
            )
        else:
            self.options = get_signature_option(
                self.func, self.base_options, skipping_argument=1
            )


class SubCommandGroup(BaseCore, ApplicationSubcommandGroup):
    options: List[SubCommand]

    def __init__(self, func: Callable, parents, checks=None, *args, **kwargs):
        if kwargs.get("name") is None:
            kwargs["name"] = func.__name__
        self.parents: Union[Command] = parents
        super().__init__(func=func, checks=checks, *args, **kwargs)
        self.parents.options.append(self)

    def subcommand(
            self,
            name: str = None,
            description: str = "No description.",
            cls: classmethod = None,
            checks=None,
            options: Optional[List[CommandOption]] = None,
    ):
        if options is None:
            options = []

        if cls is None:
            cls = SubCommand

        def decorator(func):
            return cls(
                func,
                name=name,
                description=description,
                checks=checks,
                options=options,
                top_parents=self.parents,
                parents=self,
            )

        return decorator

    def set_signature_option(self) -> None:
        """Since add_interaction is called and cog information is entered in parents,
        parents value is reflected and skipping_argument value is determined.
        """
        for opt in self.options:
            opt.set_signature_option()


class BaseCommand(BaseCore):
    def __init__(
            self, func: Callable, checks=None, sync_command: bool = None, *args, **kwargs
    ):
        if kwargs.get("name") is None:
            kwargs["name"] = func.__name__
        super().__init__(func=func, checks=checks, *args, **kwargs)
        self.sync_command: bool = sync_command


class Command(BaseCommand, SlashCommand):
    def __init__(
            self,
            func: Callable,
            checks=None,
            options: List[Union[CommandOption, SubCommand, SubCommandGroup]] = None,
            sync_command: bool = None,
            **kwargs
    ):
        if options is None:
            options = []
        if hasattr(func, "__command_options__"):
            func.__command_options__.reverse()
            options += func.__command_options__
        self.base_options = options

        # options = get_signature_option(func, options)
        super().__init__(
            func=func,
            checks=checks,
            sync_command=sync_command,
            options=options,
            **kwargs
        )

    def set_signature_option(self) -> None:
        """Since add_interaction is called and cog information is entered in parents,
        parents value is reflected and skipping_argument value is determined.
        """
        if self.is_subcommand:
            for opt in self.options:
                opt.set_signature_option()
        else:
            if self.cog is not None:
                self.options = get_signature_option(
                    self.func, self.base_options, skipping_argument=2
                )
            else:
                self.options = get_signature_option(
                    self.func, self.base_options, skipping_argument=1
                )
        return

    def subcommand(
            self,
            name: str = None,
            description: str = "No description.",
            cls: classmethod = None,
            checks=None,
            options: List[CommandOption] = None,
    ):
        if options is None:
            options = []

        if cls is None:
            cls = SubCommand

        def decorator(func):
            new_cls = cls(
                func,
                name=name,
                description=description,
                checks=checks,
                options=options,
                top_parents=self,
                parents=self,
            )

            return new_cls

        return decorator

    def subcommand_group(
            self,
            name: str = None,
            description: str = "No description.",
            cls: classmethod = None,
            options: list = None,
    ):
        if options is None:
            options = []

        if cls is None:
            cls = SubCommandGroup

        def decorator(func):
            new_cls = cls(
                func, name=name, description=description, options=options, parents=self
            )
            return new_cls

        return decorator

    @property
    def is_subcommand(self) -> bool:
        for opt in self.options:
            if isinstance(opt, (SubCommand, SubCommandGroup)):
                return True
        else:
            return False


class MemberCommand(BaseCommand, UserCommand):
    pass


class ContextMenuCommand(BaseCommand, ContextMenu):
    pass


decorator_command_types = Union[Command, MemberCommand, ContextMenuCommand]


def command(
        name: str = None,
        description: str = "No description.",
        cls: classmethod = None,
        checks=None,
        options: List[CommandOption] = None,
        sync_command: bool = None,
):
    if options is None:
        options = []

    if cls is None:
        cls = Command

    def decorator(func):
        return cls(
            func,
            name=name,
            description=description,
            checks=checks,
            options=options,
            sync_command=sync_command,
        )

    return decorator


def user(
        name: str = None,
        cls: classmethod = None,
        checks=None,
        sync_command: bool = None,
):
    if cls is None:
        cls = MemberCommand

    def decorator(func):
        return cls(func, name=name, checks=checks, sync_command=sync_command)

    return decorator


def context(
        name: str = None,
        cls: classmethod = None,
        checks=None,
        sync_command: bool = None,
):
    if cls is None:
        cls = ContextMenuCommand

    def decorator(func):
        return cls(func, name=name, checks=checks, sync_command=sync_command)

    return decorator


def get_signature_option(func, options, skipping_argument: int = 1):
    signature_arguments = inspect.signature(func).parameters
    arguments = []
    signature_arguments_count = len(signature_arguments) - skipping_argument

    if len(options) == 0 and len(signature_arguments) > skipping_argument - 1:
        for _ in range(signature_arguments_count):
            options.append(CommandOption())
    elif signature_arguments_count > len(options):
        for _ in range(signature_arguments_count - len(options)):
            options.append(CommandOption())
    elif signature_arguments_count < len(options):
        raise TypeError("number of options and the number of arguments are different.")

    sign_arguments = list(signature_arguments.values())
    for arg in sign_arguments[skipping_argument:]:
        arguments.append(arg)

    for index, opt in enumerate(options):
        options[index].parameter_name = arguments[index].name
        if opt.name is None:
            options[index].name = arguments[index].name
        if opt.required or arguments[index].default == arguments[index].empty:
            options[index].required = True
        if opt.type is None:
            options[index].type = arguments[index].annotation

        # Check Empty Option
        if arguments[index].annotation is None:
            del options[index]

    return options