# Hermes impact track: completeness check and adjudication

Reference classes (refs.py + lsp_def.py, every NAME token / alias / string / comment equal to the name in the 2383 in-scope files):
gt = on a pyright site line; def = a declaration of any same-named symbol; import; comment; string (prose) / string-exact (whole literal == name, read);
res-other = pyright go-to-definition resolves to a different declaration; res-skip-attr = `x.name` to a module function in a file that never names its module;
res-unresolved / res-TARGET = read by hand (verdicts below).

## format_bytes (hermes_cli/sizefmt.py:7) - SELECTED
- role alias; probe positional; sites 24 = 24 pyright + 0 adjudicated (share 0%, limit 20%); 10 files
- platform-only pyright sites: none
- reference tallies: def 1, gt 25, import 10

## _norm (hermes_cli/observability/shared_metrics_contract.py:598) - SELECTED
- role common; probe positional; sites 27 = 27 pyright + 0 adjudicated (share 0%, limit 20%); 3 files
- platform-only pyright sites: none
- reference tallies: comment 2, def 14, gt 27, import 3, res-other 63

## _write (pm/lock.py:66) - SELECTED
- role common; probe positional; sites 13 = 13 pyright + 0 adjudicated (share 0%, limit 20%); 6 files
- platform-only pyright sites: none
- reference tallies: comment 2, def 20, gt 13, import 7, res-other 50, res-skip-attr 37, string 1

## _fail (hermes_cli/plugins_cmd.py:113) - SELECTED
- role common; probe positional; sites 20 = 20 pyright + 0 adjudicated (share 0%, limit 20%); 8 files
- platform-only pyright sites: none
- reference tallies: comment 2, def 26, gt 20, import 8, res-other 161, res-skip-attr 15, res-unresolved 3, string 1
  - `hermes_cli/tools_config_cua.py:141` **not**: tools_config_cua.py defines its own module-level _fail (line 24); this call binds to that local function, not plugins_cmd._fail (pyright LSP cannot resolve it on Darwin: the line is under a win32 guard).
  - `hermes_cli/tools_config_cua.py:248` **not**: tools_config_cua.py defines its own module-level _fail (line 24); this call binds to that local function, not plugins_cmd._fail (pyright LSP cannot resolve it on Darwin: the line is under a win32 guard).
  - `hermes_cli/tools_config_cua.py:250` **not**: tools_config_cua.py defines its own module-level _fail (line 24); this call binds to that local function, not plugins_cmd._fail (pyright LSP cannot resolve it on Darwin: the line is under a win32 guard).

## _section (hermes_cli/doctor_report.py:31) - SELECTED
- role common; probe positional; sites 9 = 9 pyright + 0 adjudicated (share 0%, limit 20%); 5 files
- platform-only pyright sites: hermes_cli/doctor_platform.py:511 (Windows), hermes_cli/doctor_platform.py:592 (Darwin/Linux)
- reference tallies: def 12, gt 9, import 8, res-other 60, res-skip-attr 13, string 1

## CredentialPool.has_credentials (agent/credential_pool.py:1036) - SELECTED
- role method; probe positional; sites 27 = 27 pyright + 0 adjudicated (share 0%, limit 20%); 18 files
- platform-only pyright sites: none
- reference tallies: comment 2, def 1, gt 27

## ProviderRegistry.export (agent/provider_registry.py:161) - SELECTED
- role method; probe positional; sites 7 = 7 pyright + 0 adjudicated (share 0%, limit 20%); 7 files
- platform-only pyright sites: none
- reference tallies: comment 67, def 1, gt 7, res-other 26, string 260, string-exact 28
  - `agent/display.py:187` **not**: string literal 'export' is a shell-builtin name in a set literal, not a getattr/dynamic lookup of ProviderRegistry.export
  - `agent/monitoring/otlp_exporter.py:84` **not**: string literal 'export' is a config section key, not a getattr/dynamic lookup of ProviderRegistry.export
  - `agent/redact.py:999` **not**: string literal 'export' is a shell command name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/commands.py:120` **not**: string literal 'export' is a slash-command name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/completion.py:34` **not**: string literal 'export' is a profile subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/config_defaults.py:2105` **not**: string literal 'export' is a config key, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/console_engine.py:819` **not**: string literal 'export' is a console command words, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/kanban_boards.py:212` **not**: string literal 'export' is a CLI dispatch-table key (maps to _cmd_boards_export), not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/kanban_parser.py:125` **not**: string literal 'export' is a argparse subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/main_agent_cmds.py:144` **not**: string literal 'export' is a config key lookup, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/observability/shared_metrics_harness.py:187` **not**: string literal 'export' is a shell-builtin name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/plugin_packs.py:580` **not**: string literal 'export' is a CLI dispatch-table key (lambda -> cmd_pack_export), not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/profile_cmd.py:619` **not**: string literal 'export' is a CLI dispatch-table key (_profile_export), not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/sessions_cmd.py:1195` **not**: string literal 'export' is a CLI dispatch-table key (_cmd_export), not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/skills_hub.py:1365` **not**: string literal 'export' is a argv comparison, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/skills_hub.py:1460` **not**: string literal 'export' is a argv comparison, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/subcommands/plugins.py:176` **not**: string literal 'export' is a argparse subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/subcommands/profile.py:115` **not**: string literal 'export' is a argparse subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/subcommands/sessions.py:70` **not**: string literal 'export' is a argparse subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `hermes_cli/subcommands/skills.py:158` **not**: string literal 'export' is a argparse subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `optional-skills/blockchain/hyperliquid/scripts/hyperliquid_client.py:1635` **not**: string literal 'export' is a argparse subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `optional-skills/productivity/memento-flashcards/scripts/memento_cards.py:323` **not**: string literal 'export' is a argparse subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `optional-skills/productivity/memento-flashcards/scripts/memento_cards.py:344` **not**: string literal 'export' is a dispatch-table key (cmd_export), not a getattr/dynamic lookup of ProviderRegistry.export
  - `optional-skills/security/oss-forensics/scripts/evidence-store.py:245` **not**: string literal 'export' is a argparse subcommand name, not a getattr/dynamic lookup of ProviderRegistry.export
  - `optional-skills/security/oss-forensics/scripts/evidence-store.py:301` **not**: string literal 'export' is a argv comparison, not a getattr/dynamic lookup of ProviderRegistry.export
  - `pm/environment.py:390` **not**: string literal 'export' is a uv subcommand in argv list, not a getattr/dynamic lookup of ProviderRegistry.export
  - `pm/environment.py:397` **not**: string literal 'export' is a uv subcommand label, not a getattr/dynamic lookup of ProviderRegistry.export
  - `scripts/observability/gateway_health_export_probe.py:49` **not**: string literal 'export' is a config/JSON key, not a getattr/dynamic lookup of ProviderRegistry.export

## normalize_provider (hermes_cli/providers.py:164) - SELECTED
- role namesake; probe positional; sites 20 = 18 pyright + 2 adjudicated (share 10%, limit 20%); 9 files
- platform-only pyright sites: none
- reference tallies: comment 1, def 3, gt 18, import 24, res-TARGET 3, res-other 48
  - `hermes_cli/doctor_config.py:207` **not**: `normalize = None` initialiser of the alias variable (no call; nothing to update).
  - `hermes_cli/doctor_config.py:226` **not**: returns the alias object (no call); the call that must change is line 265.
  - `hermes_cli/doctor_config.py:265` **call**: `normalize` is normalize_provider imported as `normalize` in _known_provider_ids (line 213), returned through a tuple typed `object` (line 226) and called here; pyright cannot see the call (callee typed object), but it breaks at runtime.
  - `hermes_cli/doctor_connectivity.py:109` **call**: `_normalize_provider` is bound by `from hermes_cli.providers import normalize_provider as _normalize_provider` (line 99) with a fallback def only in the except branch; pyright resolves the name to the fallback declaration and reports nothing, but at runtime the import succeeds and this calls the target.

## UpdateLock.acquire (hermes_cli/update_lock.py:313) - spare
- role method-spare; probe positional; sites 6 = 6 pyright + 0 adjudicated (share 0%, limit 20%); 5 files
- platform-only pyright sites: none
- reference tallies: comment 32, def 11, gt 6, import 41, res-other 91, res-unresolved 10, string 65
  - `agent/auxiliary_client.py:8341` **not**: asyncio semaphore (await semaphore.acquire())
  - `agent/trajectory.py:30` **not**: local bool variable `acquire`
  - `gateway/platforms/signal.py:827` **not**: SignalAttachmentScheduler.acquire(n) (async, takes n)
  - `gateway/run_turn.py:615` **not**: SessionTurnLeaseRegistry.acquire (async)
  - `tools/mcp_oauth_manager.py:239` **not**: asyncio.Lock.acquire (SDK context.lock)
  - `tools/mcp_oauth_manager.py:262` **not**: asyncio.Lock.acquire (SDK context.lock)
  - `tools/send_message_senders.py:417` **not**: Signal scheduler acquire(n) (async)
  - `tools/wake_word.py:774` **not**: local bool parameter `acquire`
  - `tools/wake_word.py:780` **not**: local bool parameter `acquire`
  - `tui_gateway/methods_tools.py:414` **not**: threading.Lock.acquire(blocking=False)

## coerce_port (gateway/platforms/_shared.py:245) - spare
- role alias-spare; probe positional; sites 13 = 13 pyright + 0 adjudicated (share 0%, limit 20%); 10 files
- platform-only pyright sites: none
- reference tallies: def 1, gt 13, import 10

