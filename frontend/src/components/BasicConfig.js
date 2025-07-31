import React, { useState, useEffect } from 'react';
import {
  Card, CardTitle, CardBody,
  Form, FormGroup,
  TextInput,
  Checkbox,
  Select, SelectOption, SelectVariant,
  FormSelect, FormSelectOption,
  Title,
  HelperText, HelperTextItem,
  Spinner,
  Divider,
  Grid, GridItem
} from '@patternfly/react-core';
import OperatorSearch from './OperatorSearch';

function BasicConfig({ config, updateConfig, operatorMappings, ocpReleases, ocpChannels, channelReleases, onVersionChange, onChannelChange, isLoadingReleases, isLoadingChannels, isLoadingChannelReleases }) {
  // State for operator catalogs
  const [availableCatalogs, setAvailableCatalogs] = useState([]);
  const [isLoadingCatalogs, setIsLoadingCatalogs] = useState(false);

  // Fetch available catalogs when OCP version changes
  const fetchCatalogsForVersion = async (version) => {
    if (!version) {
      setAvailableCatalogs([]);
      return;
    }
    
    setIsLoadingCatalogs(true);
    try {
      const response = await fetch(`/api/operators/catalogs/${version}/list`);
      const data = await response.json();
      
      if (data.status === 'success') {
        setAvailableCatalogs(data.catalogs);
        
        // Auto-select the default catalog if no catalogs are currently selected
        if (!config.operator_catalogs || config.operator_catalogs.length === 0) {
          const defaultCatalogs = data.catalogs.filter(cat => cat.default).map(cat => cat.url);
          if (defaultCatalogs.length > 0) {
            updateConfig({ operator_catalogs: defaultCatalogs });
          }
        }
      } else {
        console.error('Failed to fetch catalogs:', data.message);
        setAvailableCatalogs([]);
      }
    } catch (error) {
      console.error('Error fetching catalogs:', error);
      setAvailableCatalogs([]);
    } finally {
      setIsLoadingCatalogs(false);
    }
  };

  // Handle catalog selection changes
  const handleCatalogSelectionChange = (selection, isSelected) => {
    const currentCatalogs = config.operator_catalogs || [];
    let newCatalogs;
    
    if (isSelected) {
      newCatalogs = [...currentCatalogs, selection];
    } else {
      newCatalogs = currentCatalogs.filter(catalog => catalog !== selection);
    }
    
    updateConfig({ operator_catalogs: newCatalogs });
  };

  const handleOcpVersionsChange = (e) => {
    const selectedOptions = Array.from(e.target.selectedOptions);
    const versions = selectedOptions.map(option => option.value);
    updateConfig({ ocp_versions: versions });
  };

  const handleSingleOcpVersionChange = (value, event) => {
    // PatternFly FormSelect can pass either (value, event) or (event) depending on version
    let selectedValue;
    
    if (typeof value === 'string') {
      // New PatternFly API: (value, event)
      selectedValue = value;
    } else if (value && value.target) {
      // Old PatternFly API or standard HTML: (event)
      selectedValue = value.target.value;
    } else {
      // Fallback
      selectedValue = '';
    }
    
    updateConfig({ ocp_versions: selectedValue ? [selectedValue] : [] });
    
    // Fetch channels for the selected version
    if (onVersionChange && selectedValue) {
      onVersionChange(selectedValue);
    }
    
    // Fetch catalogs for the selected version
    if (selectedValue) {
      fetchCatalogsForVersion(selectedValue);
    }
  };

  const handleChannelChange = (value, event) => {
    // PatternFly FormSelect can pass either (value, event) or (event) depending on version
    let selectedValue;
    
    if (typeof value === 'string') {
      // New PatternFly API: (value, event)
      selectedValue = value;
    } else if (value && value.target) {
      // Old PatternFly API or standard HTML: (event)
      selectedValue = value.target.value;
    } else {
      // Fallback
      selectedValue = '';
    }
    
    updateConfig({ 
      ocp_channel: selectedValue,
      ocp_min_version: '', // Reset min/max when channel changes
      ocp_max_version: ''
    });
    
    // Fetch releases for the selected channel
    if (onChannelChange && selectedValue) {
      onChannelChange(selectedValue);
    }
  };

  const handleMinVersionChange = (value, event) => {
    // PatternFly FormSelect can pass either (value, event) or (event) depending on version
    let selectedValue;
    
    if (typeof value === 'string') {
      // New PatternFly API: (value, event)
      selectedValue = value;
    } else if (value && value.target) {
      // Old PatternFly API or standard HTML: (event)
      selectedValue = value.target.value;
    } else {
      // Fallback
      selectedValue = '';
    }
    
    updateConfig({ ocp_min_version: selectedValue });
  };

  const handleMaxVersionChange = (value, event) => {
    // PatternFly FormSelect can pass either (value, event) or (event) depending on version
    let selectedValue;
    
    if (typeof value === 'string') {
      // New PatternFly API: (value, event)
      selectedValue = value;
    } else if (value && value.target) {
      // Old PatternFly API or standard HTML: (event)
      selectedValue = value.target.value;
    } else {
      // Fallback
      selectedValue = '';
    }
    
    updateConfig({ ocp_max_version: selectedValue });
  };

  // New handler for modern operator objects with channels
  const handleModernOperatorsChange = (operators) => {
    updateConfig({ operators });
  };

  return (
    <Grid hasGutter>
      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">OpenShift Platform Versions</Title>
          </CardTitle>
          <CardBody>
            <Form>
              <FormGroup
                label="Primary OCP Version"
                fieldId="ocp-version-single"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      Select the primary OpenShift version for your deployment
                    </HelperTextItem>
                  </HelperText>
                }
                labelIcon={isLoadingReleases && <Spinner size="sm" />}
              >
                <FormSelect
                  value={config.ocp_versions?.[0] || ''}
                  onChange={handleSingleOcpVersionChange}
                  id="ocp-version-single"
                  isDisabled={isLoadingReleases}
                >
                  <FormSelectOption
                    value=""
                    label={isLoadingReleases ? 'Loading releases...' : 'Select a version...'}
                  />
                  {ocpReleases.map(version => (
                    <FormSelectOption key={version} value={version} label={version} />
                  ))}
                </FormSelect>
              </FormGroup>

              <FormGroup
                label="OCP Channel"
                fieldId="ocp-channel"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      {config.ocp_versions?.[0] && ocpChannels.length > 0 && !isLoadingChannels
                        ? `${ocpChannels.length} channels available for version ${config.ocp_versions[0]}`
                        : isLoadingChannels
                          ? 'Loading channels for selected version...'
                          : 'Channels will be loaded when you select a version above'}
                    </HelperTextItem>
                  </HelperText>
                }
                labelIcon={isLoadingChannels && <Spinner size="sm" />}
              >
                <FormSelect
                  value={config.ocp_channel || ''}
                  onChange={handleChannelChange}
                  id="ocp-channel"
                  isDisabled={!config.ocp_versions?.[0] || isLoadingChannels}
                >
                  <FormSelectOption
                    value=""
                    label={
                      !config.ocp_versions?.[0] 
                        ? 'Select a version first...' 
                        : isLoadingChannels
                          ? 'Loading channels...'
                          : ocpChannels.length === 0 
                            ? 'No channels available' 
                            : 'Select a channel...'
                    }
                  />
                  {ocpChannels.map(channel => (
                    <FormSelectOption key={channel} value={channel} label={channel} />
                  ))}
                </FormSelect>
              </FormGroup>

              <FormGroup
                label="Minimum Release Version"
                fieldId="ocp-min-version"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      {config.ocp_channel && channelReleases.length > 0 && !isLoadingChannelReleases
                        ? `${channelReleases.length} releases available for channel ${config.ocp_channel}`
                        : isLoadingChannelReleases
                          ? 'Loading releases for selected channel...'
                          : 'Releases will be loaded when you select a channel above'}
                    </HelperTextItem>
                  </HelperText>
                }
                labelIcon={isLoadingChannelReleases && <Spinner size="sm" />}
              >
                <FormSelect
                  value={config.ocp_min_version || ''}
                  onChange={handleMinVersionChange}
                  id="ocp-min-version"
                  isDisabled={!config.ocp_channel || isLoadingChannelReleases || channelReleases.length === 0}
                >
                  <FormSelectOption
                    value=""
                    label={
                      !config.ocp_channel 
                        ? 'Select a channel first...' 
                        : isLoadingChannelReleases
                          ? 'Loading releases...'
                          : channelReleases.length === 0 
                            ? 'No releases available' 
                            : 'Select minimum version...'
                    }
                  />
                  {channelReleases.map(release => (
                    <FormSelectOption key={release} value={release} label={release} />
                  ))}
                </FormSelect>
              </FormGroup>

              <FormGroup
                label="Maximum Release Version"
                fieldId="ocp-max-version"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      Optional: Leave empty to mirror all releases from minimum version onwards
                    </HelperTextItem>
                  </HelperText>
                }
                labelIcon={isLoadingChannelReleases && <Spinner size="sm" />}
              >
                <FormSelect
                  value={config.ocp_max_version || ''}
                  onChange={handleMaxVersionChange}
                  id="ocp-max-version"
                  isDisabled={!config.ocp_channel || isLoadingChannelReleases || channelReleases.length === 0}
                >
                  <FormSelectOption
                    value=""
                    label={
                      !config.ocp_channel 
                        ? 'Select a channel first...' 
                        : isLoadingChannelReleases
                          ? 'Loading releases...'
                          : channelReleases.length === 0 
                            ? 'No releases available' 
                            : 'Select maximum version...'
                    }
                  />
                  {channelReleases.map(release => (
                    <FormSelectOption key={release} value={release} label={release} />
                  ))}
                </FormSelect>
              </FormGroup>
            </Form>
          </CardBody>
        </Card>
      </GridItem>

      <GridItem span={12}>
        <OperatorSearch 
          selectedOperators={config.operators || []}
          onOperatorsChange={handleModernOperatorsChange}
          selectedCatalogs={config.operator_catalogs || []}
          selectedVersion={config.ocp_versions?.[0] || ''}
        />
      </GridItem>

      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">Operator Catalogs</Title>
          </CardTitle>
          <CardBody>
            <Form>
              <FormGroup
                label="Operator Catalogs"
                fieldId="operator-catalogs"
                helperText={
                  <HelperText>
                    <HelperTextItem>
                      Select multiple operator catalogs based on your OCP version. Default catalog is automatically selected.
                    </HelperTextItem>
                  </HelperText>
                }
              >
                {isLoadingCatalogs ? (
                  <Spinner size="md" />
                ) : (
                  <div>
                    {availableCatalogs.length > 0 ? (
                      <div>
                        {availableCatalogs.map((catalog, index) => (
                          <div key={index} style={{ marginBottom: '0.5rem' }}>
                            <Checkbox
                              label={
                                <div>
                                  <strong>
                                    {catalog.name}
                                    {catalog.validated && (
                                      <span style={{ color: 'var(--pf-global--success-color--100)', marginLeft: '0.5rem' }}>
                                        ✓
                                      </span>
                                    )}
                                    {!catalog.validated && catalog.error && (
                                      <span style={{ color: 'var(--pf-global--warning-color--100)', marginLeft: '0.5rem' }}>
                                        ⚠
                                      </span>
                                    )}
                                  </strong>
                                  {catalog.operators_count > 0 && (
                                    <span style={{ color: 'var(--pf-global--info-color--100)', marginLeft: '0.5rem', fontSize: '0.8em' }}>
                                      ({catalog.operators_count} operators)
                                    </span>
                                  )}
                                  <br />
                                  <small style={{ color: 'var(--pf-global--Color--200)' }}>
                                    {catalog.url}
                                  </small>
                                  <br />
                                  <small style={{ fontStyle: 'italic' }}>
                                    {catalog.description}
                                    {catalog.error && (
                                      <span style={{ color: 'var(--pf-global--warning-color--100)' }}>
                                        {' '}- {catalog.error}
                                      </span>
                                    )}
                                  </small>
                                </div>
                              }
                              isChecked={(config.operator_catalogs || []).includes(catalog.url)}
                              onChange={(checked) => handleCatalogSelectionChange(catalog.url, checked)}
                              id={`catalog-${index}`}
                            />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <TextInput
                        value={(config.operator_catalogs || []).join(', ')}
                        onChange={(value) => {
                          const catalogs = value.split(',').map(c => c.trim()).filter(c => c.length > 0);
                          updateConfig({ operator_catalogs: catalogs });
                        }}
                        id="operator-catalogs-manual"
                        placeholder="registry.redhat.io/redhat/redhat-operator-index:v4.18"
                        helperText="Enter comma-separated catalog URLs"
                      />
                    )}
                  </div>
                )}
              </FormGroup>
            </Form>
          </CardBody>
        </Card>
      </GridItem>

      <GridItem span={12}>
        <Card>
          <CardTitle>
            <Title headingLevel="h2">Output Configuration</Title>
          </CardTitle>
          <CardBody>
            <Form>
              <FormGroup
                label="Output File Name"
                fieldId="output-file"
              >
                <TextInput
                  value={config.output_file || ''}
                  onChange={(value) => updateConfig({ output_file: value })}
                  id="output-file"
                  placeholder="imageset-config.yaml"
                />
              </FormGroup>
            </Form>
          </CardBody>
        </Card>
      </GridItem>
    </Grid>
  );
}

export default BasicConfig;
