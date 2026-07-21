import Link from "next/link";

export const metadata = {
  title: "Terms of Service -- SEO Repair Kit",
};

export default function TermsOfServicePage() {
  return (
    <div className="flex flex-1 flex-col items-center bg-neutral-950">
      <main className="w-full max-w-2xl px-6 py-16 text-neutral-300">
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-300">
          &larr; Back to SEO Repair Kit
        </Link>
        <h1 className="mt-6 text-3xl font-semibold text-neutral-50">Terms of Service</h1>
        <p className="mt-2 text-sm text-neutral-500">Last updated: July 20, 2026</p>

        <div className="mt-8 flex flex-col gap-6 text-sm leading-relaxed">
          <p>
            These terms govern your use of SEO Repair Kit (the "service"). By creating an account or
            using the service, you agree to them.
          </p>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">The service</h2>
            <p>
              SEO Repair Kit audits websites you provide for SEO and technical health issues, tracks
              results over time, and -- if you connect your own Gmail account -- lets you send audit
              reports to a recipient of your choosing. Some features are free; others require a paid
              plan or usage credits, as shown in the product at the time of use.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Your account</h2>
            <p>
              You're responsible for the activity on your account and for keeping your sign-in
              credentials secure. You must provide accurate information and not share your account
              with others in a way that circumvents usage limits or billing.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Connecting Gmail</h2>
            <p>
              If you grant the service permission to send email through your Gmail account, you're
              responsible for the content and recipients of any email you choose to send through it.
              You agree not to use this feature to send unsolicited bulk email, spam, or anything that
              violates Google's own program policies or applicable anti-spam law (e.g. CAN-SPAM,
              CASL, GDPR's e-privacy rules). We may suspend this feature for an account if we
              reasonably believe it's being used to send unwanted or abusive email.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Acceptable use</h2>
            <p>
              You may only audit domains you own or have permission to audit, and only use share
              links, PDFs, or emailed reports for legitimate purposes such as your own site
              management or a good-faith pitch to a site's owner. You may not use the service to
              scan, harass, or send unwanted communications to third parties at scale.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Report accuracy</h2>
            <p>
              Audit results and AI-visibility checks are automated best-effort assessments, not
              guarantees. We don't warrant that following any recommendation will improve search
              rankings, AI-assistant citations, or any other outcome.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Availability &amp; changes</h2>
            <p>
              We may modify, suspend, or discontinue any part of the service, and may update these
              terms from time to time. Continued use after an update means you accept the revised
              terms.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Limitation of liability</h2>
            <p>
              The service is provided "as is" without warranties of any kind. To the extent
              permitted by law, we're not liable for indirect, incidental, or consequential damages
              arising from your use of the service.
            </p>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium text-neutral-100">Contact</h2>
            <p>
              Questions about these terms:{" "}
              <a href="mailto:support@seorepairkit.com" className="text-neutral-100 underline hover:text-neutral-300">
                support@seorepairkit.com
              </a>
              .
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
