import React from 'react';
import {
  Card,
  CardTitle,
  CardBody,
  Button,
  Grid,
  GridItem,
  Title,
  Text,
  TextContent,
  Alert,
  CodeBlock,
  CodeBlockCode,
  ActionGroup
} from '@patternfly/react-core';
import { DownloadIcon, PlayIcon } from '@patternfly/react-icons';
import LoadingSpinner from './LoadingSpinner';

function PreviewGenerate({ config, yamlPreview, isGenerating, onGeneratePreview, onDownloadConfig }) {
  const hasAnyConfig = () => {
    return (
      (config.ocp_versions && config.ocp_versions.length > 0) ||
      (config.operators && config.operators.length > 0) ||
      (config.additional_images && config.additional_images.length > 0) ||
      (config.helm_charts && config.helm_charts.length > 0)
    );
  };

  const renderConfigSummary = () => {
    return (
      <Card>
        <CardTitle>
          <Title headingLevel="h2">Configuration Summary</Title>
        </CardTitle>
        <CardBody>
          {config.ocp_versions && config.ocp_versions.length > 0 && (
            <TextContent style={{ marginBottom: '1rem' }}>
              <Text><strong>OCP Versions:</strong> {config.ocp_versions.join(', ')}</Text>
              <Text><strong>Channel:</strong> {config.ocp_channel}</Text>
              {config.ocp_min_version && (
                <Text><strong>Min Version:</strong> {config.ocp_min_version}</Text>
              )}
              {config.ocp_max_version && (
                <Text><strong>Max Version:</strong> {config.ocp_max_version}</Text>
              )}
            </TextContent>
          )}

          {config.operators && config.operators.length > 0 && (
            <TextContent style={{ marginBottom: '1rem' }}>
              <Text><strong>Operators:</strong></Text>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem' }}>
                {config.operators.map((op, idx) => (
                  <li key={idx}>
                    {typeof op === 'string' ? op : op.name}
                    {op.channel && (
                      <span style={{ color: '#6a6e73', marginLeft: 8 }}>
                        (channel: {op.channel})
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <Text><strong>Catalogs:</strong> {
                (config.operator_catalogs && config.operator_catalogs.length > 0) 
                  ? config.operator_catalogs.join(', ')
                  : (config.operator_catalog || 'None specified')
              }</Text>
            </TextContent>
          )}

          {config.additional_images && config.additional_images.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <Text><strong>Additional Images:</strong></Text>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem' }}>
                {config.additional_images.map((image, index) => (
                  <li key={index}>{image}</li>
                ))}
              </ul>
            </div>
          )}

          {config.helm_charts && config.helm_charts.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <Text><strong>Helm Charts:</strong></Text>
              <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem' }}>
                {config.helm_charts.map((chart, index) => (
                  <li key={index}>
                    {chart.name} - {chart.repository}
                    {chart.version && ` (v${chart.version})`}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {config.kubevirt_container && (
            <TextContent style={{ marginBottom: '1rem' }}>
              <Text><strong>KubeVirt Container:</strong> Enabled</Text>
            </TextContent>
          )}

          {!hasAnyConfig() && (
            <Alert
              variant="warning"
              title="No configuration specified"
            >
              Please go to the Basic Configuration or Advanced tabs to configure your ImageSetConfiguration.
            </Alert>
          )}
        </CardBody>
      </Card>
    );
  };

  return (
    <Grid hasGutter>
      <GridItem span={12}>
        {renderConfigSummary()}
      </GridItem>

      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">Generate Configuration</Title>
          </CardTitle>
          <CardBody>
            <ActionGroup>
              <Button
                variant="primary"
                onClick={onGeneratePreview}
                isDisabled={isGenerating || !hasAnyConfig()}
                icon={isGenerating ? <LoadingSpinner size="small" inline /> : <PlayIcon />}
              >
                {isGenerating ? 'Generating...' : 'Generate Preview'}
              </Button>
              
              <Button
                variant="secondary"
                onClick={onDownloadConfig}
                isDisabled={isGenerating || !hasAnyConfig()}
                icon={<DownloadIcon />}
              >
                Generate & Download
              </Button>
            </ActionGroup>

            {!hasAnyConfig() && (
              <Alert
                variant="info"
                title="Configuration Required"
                style={{ marginTop: '1rem' }}
              >
                Configure at least one section (OCP versions, operators, additional images, or Helm charts) to generate the ImageSetConfiguration.
              </Alert>
            )}
          </CardBody>
        </Card>
      </GridItem>

      {yamlPreview && (
        <GridItem span={12}>
          <Card>
            <CardTitle>
              <Title headingLevel="h2">Generated YAML Preview</Title>
            </CardTitle>
            <CardBody>
              <CodeBlock>
                <CodeBlockCode>{yamlPreview}</CodeBlockCode>
              </CodeBlock>
              
              <ActionGroup style={{ marginTop: '1rem' }}>
                <Button
                  variant="link"
                  onClick={() => navigator.clipboard.writeText(yamlPreview)}
                >
                  Copy to Clipboard
                </Button>
              </ActionGroup>
            </CardBody>
          </Card>
        </GridItem>
      )}

      {yamlPreview && (
        <GridItem span={12}>
          <Card>
            <CardTitle>
              <Title headingLevel="h2">Usage Instructions</Title>
            </CardTitle>
            <CardBody>
              <TextContent>
                <Text>
                  Once you have downloaded the ImageSetConfiguration file, you can use it with the oc-mirror tool:
                </Text>
              </TextContent>
              
              <CodeBlock style={{ marginTop: '1rem' }}>
                <CodeBlockCode>
{`# Mirror to disk
oc-mirror --config ${config.output_file || 'imageset-config.yaml'} file://mirror-output

# Mirror to registry
oc-mirror --config ${config.output_file || 'imageset-config.yaml'} docker://your-registry.example.com:5000`}
                </CodeBlockCode>
              </CodeBlock>
              
              <TextContent style={{ marginTop: '1rem' }}>
                <Text>
                  <strong>Note:</strong> Make sure you have the oc-mirror tool installed and configured before running these commands.
                </Text>
              </TextContent>
            </CardBody>
          </Card>
        </GridItem>
      )}
    </Grid>
  );
}

export default PreviewGenerate;
