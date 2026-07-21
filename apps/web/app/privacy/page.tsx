import Link from "next/link";

export const metadata = {
  title: "Privacy Policy -- SEO Repair Kit",
};

export default function PrivacyPolicyPage() {
  return (
    <div className="flex flex-1 flex-col items-center bg-neutral-950">
      <main className="w-full max-w-2xl px-6 py-16 text-neutral-300">
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-300">
          &larr; Back to SEO Repair Kit
        </Link>
        <h1 className="mt-6 text-3xl font-semibold text-neutral-50">Privacy Policy</h1>
        <p className="mt-2 text-sm text-neutral-500">Last updated: July 20, 2026</p>

        <div className="mt-8 flex flex-col gap-6 text-sm leading-relaxed">
          <p>
            SEO Repair Kit ("we", "our", "the service") audits websites for SEO and technical
            health issues and lets signed-in users email the resulting reports. This page explains
            what data we collect, why, and -- specifically -- what we do with Google account access
            if you choose to connect it.
          </p>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Account &amp; sign-in data</h2>
            <p>
              We use Clerk to handle sign-in. If you sign in with Google, Clerk shares your name,
              email address, and profile image with us so we can create your account. We don't
              receive or store your Google password -- authentication is handled entirely by
              Clerk and Google.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Gmail send permission</h2>
            <p>
              The scheduled-monitoring feature lets you email an audit report to a third party (for
              example, a site owner you're pitching a fix to) directly from your own Gmail address,
              rather than from a generic "no-reply" address. To do this, we ask for Google's{" "}
              <code className="rounded bg-neutral-800 px-1 py-0.5 text-xs">gmail.send</code> permission.
            </p>
            <ul className="mt-3 list-disc pl-5">
              <li>
                We can <strong>only send email</strong> through your Gmail account -- we cannot read
                your inbox, your contacts, or any message you've sent or received.
              </li>
              <li>
                We only send a message when you explicitly click "Send report now" or when a
                schedule you configured yourself comes due. We never send on your behalf without
                that trigger.
              </li>
              <li>
                Every message we send is generated from your audit data and any personal note you
                typed into the monitoring form -- we don't send anything else.
              </li>
              <li>
                Granting this permission is optional and only requested when you choose to connect
                Gmail. You can revoke it at any time from your Google Account's
                {" "}
                <a
                  href="https://myaccount.google.com/permissions"
                  target="_blank"
                  rel="noreferrer"
                  className="text-neutral-100 underline hover:text-neutral-300"
                >
                  third-party access settings
                </a>
                .
              </li>
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Audit &amp; project data</h2>
            <p>
              We store the domains you audit, the findings each audit produces, and any monitoring
              configuration (schedule, recipient email, personal message) you set up, so we can show
              you history and comparisons over time. Anonymous scans run from the homepage are not
              tied to an account and are retained only long enough to display the result.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Shared reports</h2>
            <p>
              If you generate a share link or PDF for a report, anyone with that link can view it
              without signing in. You control when a share link is created and can revoke it at any
              time.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Third-party processors</h2>
            <p>
              We use Clerk (authentication), Google's Gmail API (sending reports on your behalf,
              only with your permission), and infrastructure providers to run the service. We don't
              sell your data or share it with third parties for advertising.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Data retention &amp; deletion</h2>
            <p>
              We keep account and audit data for as long as your account is active. You can request
              deletion of your account and associated data at any time by contacting us below.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Contact</h2>
            <p>
              Questions about this policy or your data:{" "}
              <a href="mailto:privacy@seorepairkit.com" className="text-neutral-100 underline hover:text-neutral-300">
                privacy@seorepairkit.com
              </a>
              .
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
