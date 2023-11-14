classdef RatBerryClient
    %CLIENT Summary of this class goes here
    %   Detailed explanation goes here
    
    properties
        host
        port
        channels
    end
    
    methods
        function self = RatBerryClient(host, port)
            self.host = host;
            self.port = port;
            self.channels = struct();
        end
        
        function self = new_channel(self, name)
            assert(~isfield(self.channels, name), 'channel already exists');
            self.channels.(name) = RatBerryChannel(self.host, self.port, name);
        end

        function reply = run_command(self, command, varargin)

            ip = inputParser();
            ip.addParameter('args', struct(), @isstruct);
            ip.addParameter('channel', '', @ischar);
            v = varargin;
            ip.parse( v{:} );
            params = ip.Results;


            if numel(params.channel) >0
                [self.channels.(params.channel), reply] = self.channels.(params.channel).run_command(command, params.args);
            else
                ch = RatBerryChannel(self.host, self.port, '');
                [~, reply] = ch.run_command(command, params.args);
            end
        end

        function reply = get(self, req, varargin)

            ip = inputParser();
            ip.addParameter('channel', '', @ischar);
            v = varargin;
            ip.parse( v{:} );
            params = ip.Results;

            args.req = req;

            reply = self.run_command('GET', 'args', args, 'channel', params.channel);
        end
    end
end

