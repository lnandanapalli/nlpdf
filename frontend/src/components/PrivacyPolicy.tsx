import { Box, Container, Typography, Paper, Link as MuiLink } from '@mui/material';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export default function PrivacyPolicy() {
  return (
    <Box sx={{ minHeight: '100dvh', py: 6, px: 2, bgcolor: 'background.default' }}>
      <Container maxWidth="md">
        <MuiLink
          component={Link} to="/" underline="hover"
          sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, mb: 3, color: 'text.secondary' }}
        >
          <ArrowLeft size={16} /> Back
        </MuiLink>

        <Paper elevation={2} sx={{ p: { xs: 3, md: 5 }, borderRadius: 3 }}>
          <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
            Privacy Policy
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
            Last updated: March 8, 2026
          </Typography>

          <Section title="1. Information We Collect">
            <>
              <Typography variant="body1" color="text.secondary" sx={{ lineHeight: 1.8, mb: 1 }}>
                When you use the Service, we may collect information including but not limited to
                your email address, name, account credentials, and data about how you interact
                with the Service.
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ lineHeight: 1.8 }}>
                When you process files, we may collect metadata such as filenames, operation types,
                file sizes, and page counts. Uploaded files are intended to be processed temporarily
                and not stored permanently, but we make no guarantees about the timing or
                completeness of file deletion.
              </Typography>
            </>
          </Section>

          <Section title="2. How We Use Your Information">
            We use collected information to operate and provide the Service, communicate with
            you regarding your account, monitor usage, and improve the Service. We may also use
            your information as required by law or to protect our rights.
          </Section>

          <Section title="3. Third-Party Services">
            <>
              <Typography variant="body1" color="text.secondary" sx={{ lineHeight: 1.8, mb: 1 }}>
                The Service relies on third-party providers for AI processing, email delivery,
                security verification, hosting, and other functionality. Your information,
                including but not limited to your text commands, file metadata, email address,
                IP address, and browser information, may be transmitted to and processed by these
                third-party services.
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ lineHeight: 1.8 }}>
                These providers operate under their own terms and privacy policies. We have no
                control over how these third parties collect, use, or share your data. By using
                the Service, you acknowledge and accept the privacy practices of these providers.
                We encourage you to review their policies independently.
              </Typography>
            </>
          </Section>

          <Section title="4. Cookies and Tracking">
            The Service and its third-party providers may use cookies, web beacons, and similar
            technologies to operate, maintain security, and analyze usage. By using the Service,
            you consent to the use of such technologies.
          </Section>

          <Section title="5. Data Security">
            We implement reasonable measures to help protect your information. However, no method
            of electronic transmission or storage is completely secure, and we cannot guarantee
            absolute security. This is an open-source portfolio project and is not designed or
            intended to meet the requirements of any specific security or compliance standard.
            You use the Service at your own risk.
          </Section>

          <Section title="6. Data Retention">
            We retain your information for as long as your account exists or as needed to provide
            the Service. You may request deletion of your account through the Settings page. We
            will make reasonable efforts to remove your data, but we cannot guarantee that all
            copies will be immediately or completely erased from all systems, backups, or
            third-party services.
          </Section>

          <Section title="7. Your Choices">
            You may update your profile, change your password, or delete your account through
            the Settings page. Deleting your account will initiate removal of your data from
            our primary systems.
          </Section>

          <Section title="8. Children's Privacy">
            The Service is not intended for anyone under 13 years of age. We do not knowingly
            collect personal information from children under 13.
          </Section>

          <Section title="9. International Use">
            Your information may be transferred to and processed in countries other than your
            own. By using the Service, you consent to such transfers.
          </Section>

          <Section title="10. Changes to This Policy">
            We may update this policy at any time. Continued use of the Service constitutes
            acceptance of any changes. It is your responsibility to review this policy
            periodically.
          </Section>

          <Section title="11. Contact">
            This is an open-source project. For questions, please open an issue on the{' '}
            <MuiLink href="https://github.com/lnandanapalli/nlpdf" target="_blank" rel="noopener">
              GitHub repository
            </MuiLink>.
          </Section>
        </Paper>
      </Container>
    </Box>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>{title}</Typography>
      {typeof children === 'string' ? (
        <Typography variant="body1" color="text.secondary" sx={{ lineHeight: 1.8 }}>
          {children}
        </Typography>
      ) : (
        children
      )}
    </Box>
  );
}
