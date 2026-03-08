import { Box, Container, Typography, Paper, Link as MuiLink } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export default function TermsOfService() {
  const navigate = useNavigate();

  return (
    <Box sx={{ minHeight: '100dvh', py: 6, px: 2, bgcolor: 'background.default' }}>
      <Container maxWidth="md">
        <MuiLink
          component="button" underline="hover" onClick={() => navigate(-1)}
          sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, mb: 3, color: 'text.secondary' }}
        >
          <ArrowLeft size={16} /> Back
        </MuiLink>

        <Paper elevation={2} sx={{ p: { xs: 3, md: 5 }, borderRadius: 3 }}>
          <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
            Terms of Service
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
            Last updated: March 8, 2026
          </Typography>

          <Section title="1. Acceptance of Terms">
            By accessing or using NLPDF ("the Service"), you acknowledge that you have read,
            understood, and agree to be bound by these Terms of Service and our Privacy Policy.
            If you do not agree, you must immediately stop using the Service.
          </Section>

          <Section title="2. Nature of the Service">
            NLPDF is an open-source, experimental project created for educational and portfolio
            purposes. It is not a commercial product. The Service may be modified, suspended, or
            discontinued at any time without notice. You use the Service entirely at your own risk.
          </Section>

          <Section title="3. No Warranty">
            THE SERVICE IS PROVIDED ON AN "AS IS" AND "AS AVAILABLE" BASIS, WITHOUT WARRANTIES
            OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF
            MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, ACCURACY,
            RELIABILITY, OR AVAILABILITY. NO ADVICE OR INFORMATION, WHETHER ORAL OR WRITTEN,
            OBTAINED THROUGH THE SERVICE SHALL CREATE ANY WARRANTY.
          </Section>

          <Section title="4. Limitation of Liability">
            TO THE FULLEST EXTENT PERMITTED BY LAW, THE DEVELOPER AND ANY CONTRIBUTORS SHALL
            NOT BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR
            PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO LOSS OF DATA, LOSS OF PROFITS, LOSS
            OF GOODWILL, BUSINESS INTERRUPTION, OR ANY OTHER DAMAGES ARISING OUT OF OR RELATED
            TO YOUR USE OF OR INABILITY TO USE THE SERVICE, REGARDLESS OF THE CAUSE OF ACTION
            OR THE THEORY OF LIABILITY, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
          </Section>

          <Section title="5. Assumption of Risk">
            You acknowledge and agree that your use of the Service is at your sole risk. You are
            solely responsible for any files you upload, any content you process, and any
            consequences arising from your use of the Service. You should not rely on the Service
            for critical, sensitive, or irreplaceable data.
          </Section>

          <Section title="6. Third-Party Services">
            The Service relies on third-party providers for core functionality, including but
            not limited to AI processing, email delivery, security verification, and hosting.
            These providers operate under their own terms and privacy policies, which you are
            also subject to. The developer has no control over, and assumes no responsibility
            for, the content, practices, or policies of any third-party services.
          </Section>

          <Section title="7. User Conduct">
            You agree not to use the Service for any unlawful purpose or in a manner that could
            damage, disable, overburden, or impair the Service. You must not upload files that
            contain illegal, malicious, or infringing content. You are responsible for
            maintaining the security of your account credentials.
          </Section>

          <Section title="8. Account Termination">
            The developer reserves the right to suspend or terminate your access at any time,
            for any reason, with or without notice. You may delete your account at any time.
          </Section>

          <Section title="9. Indemnification">
            You agree to indemnify, defend, and hold harmless the developer and any contributors
            from and against any claims, liabilities, damages, losses, and expenses (including
            reasonable legal fees) arising out of or in any way connected with your access to or
            use of the Service, your violation of these Terms, or your violation of any rights
            of another party.
          </Section>

          <Section title="10. Changes to Terms">
            These terms may be updated at any time. Your continued use of the Service after any
            changes constitutes acceptance of the new terms. It is your responsibility to review
            these terms periodically.
          </Section>

          <Section title="11. Severability">
            If any provision of these Terms is found to be unenforceable or invalid, that
            provision shall be limited or eliminated to the minimum extent necessary, and the
            remaining provisions shall remain in full force and effect.
          </Section>

          <Section title="12. Governing Law">
            These Terms shall be governed by and construed in accordance with applicable law,
            without regard to conflict of law principles.
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
      <Typography variant="body1" color="text.secondary" sx={{ lineHeight: 1.8 }}>
        {children}
      </Typography>
    </Box>
  );
}
