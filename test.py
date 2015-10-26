#! /usr/bin/env nosetests

import duct
from duct import cmd, sh, DEVNULL, STDOUT, STDERR
from pathlib import Path
from nose.tools import eq_, raises, assert_raises
import os
import tempfile


def test_hello_world():
    out = sh('echo "hello  world"').read()
    eq_("hello  world", out)


def test_result():
    result = sh('echo more stuff').run(stdout=str)
    eq_("more stuff\n", result.stdout)


def test_bytes():
    out = sh('head -c 10 /dev/zero').read(stdout=bytes)
    eq_(b'\x00'*10, out)


@raises(duct.CheckedError)
def test_nonzero_status_throws():
    cmd('false').run()


def test_check():
    # Test both the top level and command level check params.
    eq_(1, cmd('false').run(check=False).status)
    eq_(0, cmd('false', check=False).run().status)


def test_pipe():
    out = sh('head -c 3 /dev/zero').pipe('sed', 's/./a/g').read()
    eq_("aaa", out)


def test_then():
    eq_('hi', cmd('true').then('echo', 'hi').read())
    eq_('', cmd('false').then('echo', 'hi').read(check=False))


def test_nesting():
    innermost = cmd('true').then('cat')
    middle = cmd('true').then(innermost)
    out = sh('echo hi').pipe(middle).read()
    eq_('hi', out)


def test_cwd():
    # Test cwd at both the top level and the command level, and that either can
    # be a pathlib Path.
    eq_('/tmp', cmd('pwd').read(cwd='/tmp'))
    eq_('/tmp', cmd('pwd').read(cwd=Path('/tmp')))
    eq_('/tmp', cmd('pwd', cwd='/tmp').read(cwd='/something/else'))
    eq_('/tmp', cmd('pwd', cwd=Path('/tmp')).read(cwd='/something/else'))


def test_env():
    # Test env at both the top level and the command level, and that values can
    # be pathlib Paths.
    eq_("/", sh("bash -c 'echo $x'").read(env={'x': '/'}))
    eq_("/", sh("bash -c 'echo $x'").read(env={'x': Path('/')}))
    eq_("/", sh("bash -c 'echo $x'", env={'x': '/'}).read())
    eq_("/", sh("bash -c 'echo $x'", env={'x': Path('/')}).read())


def test_full_env():
    eq_("", sh("bash -c 'echo $x'", full_env={}).read(env={'x': 'X'}))


@raises(ValueError)
def test_env_with_full_env_throws():
    # This should throw even before the command is run.
    cmd("foo", env={}, full_env={})


@raises(ValueError)
def test_input_with_stdin_throws():
    # This should throw even before the command is run.
    cmd("foo", input="foo", stdin="foo")


@raises(TypeError)
def test_undefined_keyword_throws():
    # This should throw even before the command is run.
    cmd("foo", junk_keyword=True)


def test_input():
    out = cmd('sha1sum').read(input="foo")
    eq_('0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33  -', out)


def test_stdin():
    tempfd, temp = tempfile.mkstemp()
    with os.fdopen(tempfd, 'w') as f:
        f.write('foo')
    expected = '0beec7b5ea3f0fdbc95d0dd47f3c5bc275da8a33  -'
    # with a file path
    out = cmd('sha1sum').read(stdin=temp)
    eq_(expected, out)
    # with a Path path
    out = cmd('sha1sum').read(stdin=Path(temp))
    eq_(expected, out)
    # with an open file
    with open(temp) as f:
        out = cmd('sha1sum').read(stdin=f)
        eq_(expected, out)
    # with explicit DEVNULL
    out = cmd('sha1sum').read(stdin=DEVNULL)
    eq_('da39a3ee5e6b4b0d3255bfef95601890afd80709  -', out)


def test_stdout():
    # with a file path
    with tempfile.NamedTemporaryFile() as temp:
        sh('echo hi').run(stdout=temp.name)
        eq_('hi\n', open(temp.name).read())
    # with a Path path
    with tempfile.NamedTemporaryFile() as temp:
        sh('echo hi').run(stdout=Path(temp.name))
        eq_('hi\n', open(temp.name).read())
    # with an open file
    with tempfile.NamedTemporaryFile() as temp:
        sh('echo hi').run(stdout=temp)
        eq_('hi\n', open(temp.name).read())
    # with explicit DEVNULL
    out = sh('echo hi', stdout=DEVNULL).read()
    eq_('', out)
    # to STDERR
    result = sh('echo hi', stdout=STDERR).run(stdout=str, stderr=str)
    eq_('', result.stdout)
    eq_('hi\n', result.stderr)
    # from stderr with STDOUT
    result = sh('echo hi 1>&2', stderr=STDOUT).run(stdout=bytes, stderr=bytes)
    eq_(b'hi\n', result.stdout)
    eq_(b'', result.stderr)
    # full swap
    result = (sh('echo hi; echo lo 1>&2', stdout=STDERR, stderr=STDOUT)
              .run(stdout=str, stderr=str))
    eq_('lo\n', result.stdout)
    eq_('hi\n', result.stderr)


def test_commands_can_be_paths():
    echo = Path('/bin/echo')
    eq_('foo', cmd(echo, 'foo').read())
    eq_('\n', sh(echo).read(trim=False))


def test_subshell():
    c = sh("echo foo >&2 ; false")
    out = c.subshell(check=False, stderr=STDOUT).read()
    eq_("foo", out)


@raises(TypeError)
def test_kwargs_prohibited_with_expression_value():
    # This should throw even before the command is run.
    cmd("foo").pipe(cmd("bar"), check=False)


def test_pipe_returns_rightmost_error():
    eq_(1, sh('true').pipe('false').run(check=False).status)
    eq_(1, cmd('false').pipe('false').run(check=False).status)
    eq_(3, cmd('false').pipe(sh('bash -c "exit 3"')).run(check=False).status)


def test_checked_error_contains_status():
    try:
        sh('bash -c "exit 123"').run()
    except duct.CheckedError as e:
        assert '123' in str(e)


def test_ThreadWithReturn_reraises_exceptions():
    def t():
        raise ZeroDivisionError
    thread = duct.ThreadWithReturn(t)
    thread.start()
    with assert_raises(ZeroDivisionError):
        thread.join()


def test_getting_reader_output_before_join_throws():
    default_context = duct.IOContext()
    _, ioargs = duct.parse_cmd_kwargs(stdout=str, stderr=str)
    with default_context.child_context(ioargs) as iocontext:
        with assert_raises(RuntimeError):
            iocontext.stdout_result()
        with assert_raises(RuntimeError):
            iocontext.stderr_result()
    # Exiting the with-block joins the reader threads, so the output accessors
    # should no longer throw.
    eq_('', iocontext.stdout_result())
    eq_('', iocontext.stderr_result())


def test_invalid_io_args():
    with assert_raises(TypeError):
        cmd('foo', input=1.0).run()
    with assert_raises(TypeError):
        cmd('foo', stdin=1.0).run()
    with assert_raises(TypeError):
        cmd('foo', stdout=1.0).run()
    with assert_raises(TypeError):
        cmd('foo', stderr=1.0).run()
