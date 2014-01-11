from libmproxy import script, flow
import tutils
import shlex
import os
import time
import mock


class TestScript:
    def test_simple(self):
        s = flow.State()
        fm = flow.FlowMaster(None, s)
        p = script.Script(
            shlex.split(tutils.test_data.path("scripts/a.py")+" --var 40",posix=(os.name != "nt")), fm
        )
        p.load()

        assert "here" in p.ns
        assert p.run("here") == (True, 41)
        assert p.run("here") == (True, 42)

        ret = p.run("errargs")
        assert not ret[0]
        assert len(ret[1]) == 2

        # Check reload
        p.load()
        assert p.run("here") == (True, 41)

    def test_duplicate_flow(self):
        s = flow.State()
        fm = flow.FlowMaster(None, s)
        fm.load_script([tutils.test_data.path("scripts/duplicate_flow.py")])
        r = tutils.treq()
        fm.handle_request(r)
        assert fm.state.flow_count() == 2
        assert not fm.state.view[0].request.is_replay()
        assert fm.state.view[1].request.is_replay()

    def test_err(self):
        s = flow.State()
        fm = flow.FlowMaster(None, s)

        s = script.Script(["nonexistent"], fm)
        tutils.raises(
            "no such file",
            s.load
        )

        s = script.Script([tutils.test_data.path("scripts")], fm)
        tutils.raises(
            "not a file",
            s.load
        )

        s = script.Script([tutils.test_data.path("scripts/syntaxerr.py")], fm)
        tutils.raises(
            script.ScriptError,
            s.load
        )

        s = script.Script([tutils.test_data.path("scripts/loaderr.py")], fm)
        tutils.raises(
            script.ScriptError,
            s.load
        )

    def test_concurrent(self):
        s = flow.State()
        fm = flow.FlowMaster(None, s)
        fm.load_script([tutils.test_data.path("scripts/concurrent_decorator.py")])

        with mock.patch("libmproxy.controller.DummyReply.__call__") as m:
            r1, r2 = tutils.treq(), tutils.treq()
            t_start = time.time()
            fm.handle_request(r1)
            r1.reply()
            fm.handle_request(r2)
            r2.reply()

            # Two instantiations
            assert m.call_count == 2
            assert (time.time() - t_start) < 0.09
            time.sleep(0.2)
            # Plus two invocations
            assert m.call_count == 4

    def test_concurrent2(self):
        s = flow.State()
        fm = flow.FlowMaster(None, s)
        s = script.Script([tutils.test_data.path("scripts/concurrent_decorator.py")], fm)
        s.load()
        f = tutils.tflow_full()
        f.error = tutils.terr(f.request)
        f.reply = f.request.reply

        with mock.patch("libmproxy.controller.DummyReply.__call__") as m:
            s.run("clientconnect", f)
            s.run("serverconnect", f)
            s.run("response", f)
            s.run("error", f)
            s.run("clientdisconnect", f)
            time.sleep(0.1)
            assert m.call_count == 5

    def test_concurrent_err(self):
        s = flow.State()
        fm = flow.FlowMaster(None, s)
        s = script.Script([tutils.test_data.path("scripts/concurrent_decorator_err.py")], fm)
        tutils.raises(
            "decorator not supported for this method",
            s.load
        )