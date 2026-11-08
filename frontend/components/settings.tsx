"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  Check,
  CircleCheck,
  Copy,
  KeyRound,
  LoaderCircle,
  LogIn,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardAction,
  CardContent,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  cancelChatwootLogin,
  getLoginState,
  openChatwootLogin,
  probeEnvironment,
  saveChatwoot,
  saveModelKey,
  saveSearchKey,
} from "@/lib/task-api";
import type { LoginState } from "@/lib/task-types";
import { AppShell } from "./app-shell";
import { useConnections } from "./providers";
import { ErrorNotice } from "./ui";

const SETUP =
  "python3 infra/chatwoot/setup.py\ncd infra/chatwoot\ndocker compose run --rm rails bundle exec rails db:chatwoot_prepare\ndocker compose run --rm rails bundle exec rails runner /app/appdna/seed.rb\ndocker compose up -d rails sidekiq\ncd ../../backend\npython -m playwright install chromium\npython scripts/import_chatwoot_connection.py";

export function SettingsPage() {
  const { connections, connectionError, refreshConnections } = useConnections();
  const [modelKey, setModelKey] = useState("");
  const [searchKey, setSearchKey] = useState("");
  const [token, setToken] = useState("");
  const [url, setUrl] = useState("");
  const [account, setAccount] = useState(1);
  const [inbox, setInbox] = useState(1);
  const [sandbox, setSandbox] = useState(false);
  const [pending, setPending] = useState("");
  const [error, setError] = useState("");
  const [probe, setProbe] = useState<{
    reachable: boolean;
    message: string;
  } | null>(null);
  const [login, setLogin] = useState<LoginState | null>(null);
  const [setup, setSetup] = useState(false);
  const saved = connections?.chatwoot;
  useEffect(() => {
    if (saved) {
      setUrl(saved.url);
      setAccount(saved.account_id);
      setInbox(saved.inbox_id);
      setSandbox(saved.test_environment);
    }
  }, [saved?.url, saved?.account_id, saved?.inbox_id, saved?.test_environment]);
  useEffect(() => {
    if (!login || !["opening", "waiting"].includes(login.status)) return;
    let active = true;
    const timer = window.setInterval(() => {
      getLoginState()
        .then(async (next) => {
          if (!active) return;
          setLogin(next);
          if (next.status === "connected") {
            await refreshConnections();
            toast.success("Chatwoot sign-in saved");
          }
        })
        .catch(() => {
          if (active)
            setLogin({
              status: "failed",
              message: "The sign-in status is unavailable. Please retry.",
            });
        });
    }, 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [login?.status, refreshConnections]);
  async function saveKey(
    event: FormEvent<HTMLFormElement>,
    kind: "model" | "search",
  ) {
    event.preventDefault();
    setPending(kind);
    setError("");
    try {
      if (kind === "model") {
        await saveModelKey(modelKey);
        setModelKey("");
      } else {
        await saveSearchKey(searchKey);
        setSearchKey("");
      }
      await refreshConnections();
      toast.success(kind === "model" ? "API key saved" : "Search key saved");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The key could not be saved.",
      );
    } finally {
      setPending("");
    }
  }
  async function saveTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending("chatwoot");
    setError("");
    try {
      await saveChatwoot({
        url,
        account_id: account,
        inbox_id: inbox,
        api_token: token || undefined,
        test_environment: sandbox,
      });
      setToken("");
      setProbe(null);
      await refreshConnections();
      toast.success("Chatwoot settings saved");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The connection could not be saved.",
      );
    } finally {
      setPending("");
    }
  }
  async function check() {
    setPending("probe");
    setError("");
    try {
      const state = await probeEnvironment();
      setProbe({
        reachable: !!state.reachable,
        message: state.reachable
          ? "Chatwoot is responding"
          : "Chatwoot is not reachable at this address",
      });
      await refreshConnections();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The connection check failed.",
      );
    } finally {
      setPending("");
    }
  }
  async function signIn() {
    setPending("login");
    setError("");
    try {
      setLogin(await openChatwootLogin());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Chatwoot could not be opened.",
      );
    } finally {
      setPending("");
    }
  }
  async function closeLogin() {
    setLogin(null);
    await cancelChatwootLogin().catch(() =>
      toast.error("The sign-in window could not be closed."),
    );
  }
  function refresh() {
    setError("");
    void refreshConnections().catch((err) => setError(err.message));
  }
  const dirty =
    !!saved &&
    (url !== saved.url ||
      account !== saved.account_id ||
      inbox !== saved.inbox_id ||
      sandbox !== saved.test_environment ||
      !!token);
  return (
    <AppShell section="Settings">
      <main className="app-page">
        <div className="page-heading">
          <h1>Connections</h1>
          <Button variant="outline" onClick={refresh}>
            <RefreshCw />
            Refresh
          </Button>
        </div>
        {error || connectionError ? (
          <ErrorNotice message={error || connectionError} retry={refresh} />
        ) : null}
        {!connections ? (
          connectionError ? null : (
            <Skeleton className="h-80" />
          )
        ) : (
          <>
            <div className="connections-grid">
              <Card className="model-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <KeyRound className="size-4 text-primary" />
                    AI model
                  </CardTitle>
                  <CardAction>
                    <Badge
                      variant="outline"
                      className={
                        connections.model.api_key_saved
                          ? "status-success"
                          : "status-neutral"
                      }
                    >
                      {connections.model.api_key_saved ? (
                        <Check className="size-3" />
                      ) : null}
                      {connections.model.api_key_saved
                        ? "Key saved"
                        : "Key needed"}
                    </Badge>
                  </CardAction>
                </CardHeader>
                <CardContent>
                  <form
                    className="form-stack"
                    onSubmit={(event) => saveKey(event, "model")}
                  >
                    <div className="field">
                      <Label htmlFor="provider">Provider</Label>
                      <Input id="provider" value="H Company" readOnly />
                    </div>
                    <div className="field">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="model-key">API key</Label>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span
                              className="text-muted-foreground"
                              tabIndex={0}
                              aria-label="API key storage"
                            >
                              <KeyRound className="size-3.5" />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            Saved in backend/.env on this computer.
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Input
                        id="model-key"
                        type="password"
                        autoComplete="new-password"
                        value={modelKey}
                        onChange={(event) => setModelKey(event.target.value)}
                        placeholder={
                          connections.model.api_key_saved
                            ? "Enter a new key to replace it"
                            : "Paste your H Company API key"
                        }
                        required
                      />
                    </div>
                    <div>
                      <Button
                        type="submit"
                        disabled={!modelKey.trim() || pending === "model"}
                      >
                        {pending === "model" ? (
                          <LoaderCircle className="animate-spin" />
                        ) : null}
                        Save API key
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Chatwoot</CardTitle>
                  <CardAction>
                    <Badge
                      variant="outline"
                      className={
                        saved?.session_saved && saved.api_token_saved
                          ? "status-success"
                          : "status-neutral"
                      }
                    >
                      {saved?.session_saved && saved.api_token_saved
                        ? "Sign-in saved"
                        : "Setup needed"}
                    </Badge>
                  </CardAction>
                </CardHeader>
                <CardContent>
                  <form className="form-stack" onSubmit={saveTarget}>
                    <div className="field">
                      <Label htmlFor="chatwoot-url">Chatwoot address</Label>
                      <Input
                        id="chatwoot-url"
                        type="url"
                        value={url}
                        onChange={(event) => setUrl(event.target.value)}
                        required
                      />
                    </div>
                    <div className="field">
                      <Label htmlFor="chatwoot-token">API token</Label>
                      <Input
                        id="chatwoot-token"
                        type="password"
                        autoComplete="new-password"
                        value={token}
                        onChange={(event) => setToken(event.target.value)}
                        placeholder={
                          saved?.api_token_saved
                            ? "Token saved · enter to replace"
                            : "From Chatwoot profile settings → Access token"
                        }
                        required={!saved?.api_token_saved}
                      />
                    </div>
                    <Accordion
                      type="single"
                      collapsible
                      className="connection-ids"
                    >
                      <AccordionItem value="ids">
                        <AccordionTrigger>Account and inbox</AccordionTrigger>
                        <AccordionContent>
                          <div className="form-grid">
                            <div className="field">
                              <Label htmlFor="account-id">Account ID</Label>
                              <Input
                                id="account-id"
                                type="number"
                                min={1}
                                required
                                value={account}
                                onChange={(event) =>
                                  setAccount(Number(event.target.value))
                                }
                              />
                            </div>
                            <div className="field">
                              <Label htmlFor="inbox-id">Inbox ID</Label>
                              <Input
                                id="inbox-id"
                                type="number"
                                min={1}
                                required
                                value={inbox}
                                onChange={(event) =>
                                  setInbox(Number(event.target.value))
                                }
                              />
                            </div>
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    </Accordion>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="test-account"
                        checked={sandbox}
                        onCheckedChange={(value) => setSandbox(value === true)}
                      />
                      <Label htmlFor="test-account" className="font-normal">
                        I’m using a test account
                      </Label>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <Button
                        type="submit"
                        variant="outline"
                        disabled={pending === "chatwoot"}
                      >
                        {pending === "chatwoot" ? (
                          <LoaderCircle className="animate-spin" />
                        ) : null}
                        Save connection
                      </Button>
                      <Button
                        type="button"
                        onClick={signIn}
                        disabled={
                          !saved?.test_environment ||
                          dirty ||
                          pending === "login"
                        }
                      >
                        {pending === "login" ? (
                          <LoaderCircle className="animate-spin" />
                        ) : (
                          <LogIn />
                        )}
                        {saved?.session_saved
                          ? "Sign in again"
                          : "Sign in to Chatwoot"}
                      </Button>
                    </div>
                  </form>
                  <div className="connection-actions">
                    <Button
                      variant="link"
                      onClick={check}
                      disabled={dirty || pending === "probe"}
                    >
                      {pending === "probe" ? (
                        <LoaderCircle className="animate-spin" />
                      ) : null}
                      Check connection
                    </Button>
                    <Button variant="link" onClick={() => setSetup(true)}>
                      Set up local Chatwoot
                    </Button>
                  </div>
                  {probe ? (
                    <Alert className="mt-4">
                      <AlertTitle>{probe.message}</AlertTitle>
                    </Alert>
                  ) : null}
                </CardContent>
              </Card>
            </div>
            <Accordion
              type="single"
              collapsible
              className="optional-connection"
            >
              <AccordionItem value="search">
                <AccordionTrigger>Web search · optional</AccordionTrigger>
                <AccordionContent>
                  <form
                    onSubmit={(event) => saveKey(event, "search")}
                    className="form-stack max-w-lg"
                  >
                    <div className="field">
                      <Label htmlFor="search-key">Linkup API key</Label>
                      <Input
                        id="search-key"
                        type="password"
                        value={searchKey}
                        onChange={(event) => setSearchKey(event.target.value)}
                        autoComplete="new-password"
                        placeholder={
                          connections.search.api_key_saved
                            ? "Key saved · enter to replace"
                            : "Paste your Linkup API key"
                        }
                        required
                      />
                    </div>
                    <div>
                      <Button
                        variant="outline"
                        type="submit"
                        disabled={!searchKey.trim() || pending === "search"}
                      >
                        Save search key
                      </Button>
                    </div>
                  </form>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </>
        )}
        <Dialog
          open={!!login}
          onOpenChange={(open) => {
            if (!open) void closeLogin();
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Sign in to Chatwoot</DialogTitle>
              <DialogDescription className="sr-only">
                Complete sign-in in the Chatwoot browser window.
              </DialogDescription>
            </DialogHeader>
            <div className="login-progress">
              {login?.status === "connected" ? (
                <CircleCheck className="size-10 text-primary" />
              ) : login?.status === "failed" ? null : (
                <LoaderCircle className="size-8 animate-spin text-primary" />
              )}
              <p>{login?.message}</p>
            </div>
            <DialogFooter>
              {login?.status === "failed" ? (
                <Button onClick={signIn}>Try again</Button>
              ) : null}
              <Button variant="outline" onClick={closeLogin}>
                {login?.status === "connected" ? "Done" : "Close"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Sheet open={setup} onOpenChange={setSetup}>
          <SheetContent className="detail-sheet sm:max-w-[680px]">
            <SheetHeader>
              <SheetTitle>Set up local Chatwoot</SheetTitle>
              <SheetDescription className="sr-only">
                Install the dedicated local test environment.
              </SheetDescription>
            </SheetHeader>
            <div className="sheet-body">
              <h3>1. Start Docker Desktop</h3>
              <h3>2. Run these commands from the AppDNA folder</h3>
              <div>
                <pre className="setup-code">{SETUP}</pre>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => {
                    void navigator.clipboard
                      .writeText(SETUP)
                      .then(() => toast.success("Commands copied"))
                      .catch(() => toast.error("Could not copy the commands"));
                  }}
                >
                  <Copy />
                  Copy commands
                </Button>
              </div>
              <h3>3. Refresh Connections, then sign in</h3>
              <div>
                <Button
                  onClick={() => {
                    refresh();
                    setSetup(false);
                  }}
                >
                  Refresh connections
                </Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </main>
    </AppShell>
  );
}
